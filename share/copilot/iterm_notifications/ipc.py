"""Versioned, size-bounded line-JSON protocol between the worker and its helper."""

import json
import os
import re
import select
import time
from dataclasses import dataclass
from typing import Literal, cast

from .context import HookEvent
from .diagnostics import DiagnosticError
from .worker import Action, DeliveryError


VERSION = 1
MAX_LINE = 16384
_CLASS = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}")
_KINDS = frozenset({"ready", "diagnostic", "done", "failed"})
type MessageKind = Literal["ready", "diagnostic", "done", "failed"]


@dataclass(frozen=True, slots=True)
class Message:
    kind: MessageKind
    code: str | None = None
    error: str = "Exception"


def _line(payload: dict[str, object]) -> bytes:
    return json.dumps({"v": VERSION, **payload}, separators=(",", ":")).encode() + b"\n"


def encode_message(kind: MessageKind, error: DiagnosticError | None = None) -> bytes:
    if error is None:
        return _line({"type": kind})
    cause = type(error.__cause__ or error).__name__
    return _line({"type": kind, "code": error.code, "error": cause})


def encode_request(action: Action, event: HookEvent) -> bytes:
    return _line({"action": action, "event": {
        "event": event.event, "cwd": event.cwd,
        "notification_type": event.notification_type, "source_uuid": event.source_uuid,
    }})


def _object(line: bytes) -> dict[str, object]:
    try:
        data = json.loads(line)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DeliveryError("terminal_helper_protocol") from error
    if not isinstance(data, dict) or data.get("v") != VERSION:
        raise DeliveryError("terminal_helper_protocol")
    return cast(dict[str, object], data)


def decode_message(line: bytes) -> Message:
    data = _object(line)
    kind, code, error = data.get("type"), data.get("code"), data.get("error", "Exception")
    if kind not in _KINDS or not isinstance(error, str) or not _CLASS.fullmatch(error):
        raise DeliveryError("terminal_helper_protocol")
    if kind in {"diagnostic", "failed"}:
        if not isinstance(code, str):
            raise DeliveryError("terminal_helper_protocol")
        try:
            DeliveryError(code)
        except ValueError as invalid:
            raise DeliveryError("terminal_helper_protocol") from invalid
        return Message(cast(MessageKind, kind), code, error)
    return Message(cast(MessageKind, kind))


def decode_request(line: bytes) -> tuple[Action, HookEvent]:
    data = _object(line)
    action, event = data.get("action"), data.get("event")
    if action not in {"waiting", "done"} or not isinstance(event, dict):
        raise DeliveryError("terminal_helper_protocol")
    fields = [event.get(name) for name in ("event", "cwd", "notification_type", "source_uuid")]
    name, cwd, kind, source = fields
    if not isinstance(name, str) or not isinstance(source, str) or not all(
        value is None or isinstance(value, str) for value in (cwd, kind)
    ):
        raise DeliveryError("terminal_helper_protocol")
    return cast(Action, action), HookEvent(name, cast(str | None, cwd), cast(str | None, kind), source)


class LineReader:
    """Read whole lines from a nonblocking descriptor before a monotonic deadline."""

    def __init__(self, fd: int) -> None:
        self._fd = fd
        self._buffer = bytearray()

    def read_line(self, deadline: float) -> bytes | None:
        """Return one line without its newline, or None at a clean end of stream."""
        while True:
            newline = self._buffer.find(b"\n")
            if newline > MAX_LINE or (newline < 0 and len(self._buffer) > MAX_LINE):
                raise DeliveryError("terminal_helper_reply_too_large")
            if newline >= 0:
                line = bytes(self._buffer[:newline])
                del self._buffer[:newline + 1]
                return line
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DeliveryError("terminal_helper_timeout")
            if not select.select([self._fd], [], [], remaining)[0]:
                continue
            try:
                chunk = os.read(self._fd, 65536)
            except BlockingIOError:
                continue
            if not chunk:
                if self._buffer:
                    raise DeliveryError("terminal_helper_partial_reply")
                return None
            self._buffer += chunk


def write_all(fd: int, data: bytes, deadline: float) -> None:
    view = memoryview(data)
    while view:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise DeliveryError("terminal_helper_timeout")
        if not select.select([], [fd], [], remaining)[1]:
            continue
        try:
            view = view[os.write(fd, view):]
        except BlockingIOError:
            continue
        except BrokenPipeError as error:
            raise DeliveryError("terminal_helper_exited") from error
