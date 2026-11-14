"""Per-session attention spool beside, never inside, the status helper's files.

Boundary: owner-only filesystem layout, sequence allocation, record publication,
state persistence, the permanent worker lock, and the bounded error log.
"""

import contextlib
import fcntl
import json
import os
import re
import stat
import time
from collections.abc import Iterator, Mapping
from typing import Self

from .context import EVENT_NAMES, HookEvent
from .diagnostics import DiagnosticError, diagnostic_line
from .safefs import (
    CorruptError, SpoolError, fs_code, open_checked, open_dir, open_file, read_small, write_atomic,
)
from .state import SessionState, decode_state, encode_state


ROOT_NAME = "copilot-iterm-status"
QUEUE = "notification-queue"
STATE = "notification-state.json"
WORKER_LOCK = "notification.lock"
ENQUEUE_LOCK = "notification-enqueue.lock"
SEQUENCE = "notification-sequence"
LOG = "notification-errors.log"
ENQUEUE_TIMEOUT = 2.0
LOG_LIMIT = 64 * 1024
RECORD_LIMIT = 64 * 1024
_UUID = re.compile(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")
_RECORD = re.compile(r"([0-9]{20})\.event")
_RECORD_KEYS = frozenset({"version", "seq", "event", "cwd", "notification_type", "source_uuid"})


def session_name(source_uuid: str) -> str:
    """Validate before any path use; uppercase matches iTerm2's session IDs."""
    if not _UUID.fullmatch(source_uuid):
        raise SpoolError("invalid_source_uuid")
    return source_uuid.upper()


def _encode_record(seq: int, event: HookEvent) -> bytes:
    record = json.dumps({
        "version": 1, "seq": seq, "event": event.event, "cwd": event.cwd,
        "notification_type": event.notification_type, "source_uuid": event.source_uuid,
    }, sort_keys=True).encode() + b"\n"
    if len(record) > RECORD_LIMIT:
        raise SpoolError("record_too_large")
    return record


class Spool:
    def __init__(self, source_uuid: str, fds: dict[str, int]) -> None:
        self.source_uuid = source_uuid
        self._fds = fds
        self._locked = False

    @classmethod
    def open(cls, source_uuid: str, environ: Mapping[str, str]) -> Self:
        name = session_name(source_uuid)
        fds: dict[str, int] = {}
        try:
            base = os.open(environ.get("TMPDIR") or "/tmp", os.O_RDONLY | os.O_DIRECTORY)
        except OSError as error:
            raise SpoolError("spool_unavailable") from error
        try:
            try:
                root = open_dir(ROOT_NAME, base)
            finally:
                os.close(base)
            try:
                fds["session"] = open_dir(name, root)
            finally:
                os.close(root)
            fds["queue"] = open_dir(QUEUE, fds["session"])
            for key in (WORKER_LOCK, ENQUEUE_LOCK):
                fds[key] = open_file(key, fds["session"])
        except OSError as error:
            cls._close(fds)
            raise SpoolError(fs_code(error, "spool_unavailable")) from error
        except SpoolError:
            cls._close(fds)
            raise
        return cls(source_uuid.lower(), fds)

    @staticmethod
    def _close(fds: dict[str, int]) -> None:
        for fd in fds.values():
            os.close(fd)
        fds.clear()

    def close(self) -> None:
        self._close(self._fds)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @contextlib.contextmanager
    def _enqueue_lock(self) -> Iterator[None]:
        fd = self._fds[ENQUEUE_LOCK]
        deadline = time.monotonic() + ENQUEUE_TIMEOUT
        delay = 0.001
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise SpoolError("enqueue_lock_timeout") from None
                time.sleep(min(delay, remaining))
                delay = min(delay * 2, 0.05)
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)

    def _next_sequence(self) -> int:
        raw = read_small(SEQUENCE, self._fds["session"], 32)
        counter = int(raw) if raw and raw.strip().isdigit() else 0
        queued = max(self.pending(), default=0)
        try:
            processed = self.load_state().last_seq
        except CorruptError:
            processed = 0
        return max(counter, queued, processed) + 1

    def enqueue(self, event: HookEvent) -> int:
        """Allocate the next durable sequence and atomically publish one record."""
        if event.source_uuid.lower() != self.source_uuid:
            raise SpoolError("source_mismatch")
        try:
            with self._enqueue_lock():
                seq = self._next_sequence()
                record = _encode_record(seq, event)
                write_atomic(SEQUENCE, self._fds["session"], f"{seq}\n".encode())
                write_atomic(f"{seq:020d}.event", self._fds["queue"], record)
        except OSError as error:
            raise SpoolError(fs_code(error, "queue_publish_failed")) from error
        return seq

    def pending(self) -> list[int]:
        try:
            names = os.listdir(self._fds["queue"])
        except OSError as error:
            raise SpoolError(fs_code(error, "queue_read_failed")) from error
        return sorted(int(m.group(1)) for m in map(_RECORD.fullmatch, names) if m)

    def read_record(self, seq: int) -> HookEvent:
        try:
            raw = read_small(f"{seq:020d}.event", self._fds["queue"], RECORD_LIMIT)
        except OSError as error:
            raise CorruptError(fs_code(error, "record_read_failed")) from error
        try:
            if raw is None or len(raw) > RECORD_LIMIT:
                raise ValueError("record_size")
            payload = json.loads(raw)
            if not isinstance(payload, dict) or set(payload) != _RECORD_KEYS:
                raise ValueError("record_keys")
            optional = (payload["cwd"], payload["notification_type"])
            if (
                payload["version"] != 1 or type(payload["seq"]) is not int
                or payload["seq"] != seq or payload["event"] not in EVENT_NAMES
                or payload["source_uuid"] != self.source_uuid
                or not all(value is None or isinstance(value, str) for value in optional)
            ):
                raise ValueError("record_fields")
        except (ValueError, RecursionError) as error:
            raise CorruptError("record_corrupt") from error
        return HookEvent(payload["event"], *optional, self.source_uuid)

    def remove_record(self, seq: int) -> None:
        try:
            os.unlink(f"{seq:020d}.event", dir_fd=self._fds["queue"])
        except OSError as error:
            raise SpoolError(fs_code(error, "record_remove_failed")) from error

    def load_state(self) -> SessionState:
        try:
            raw = read_small(STATE, self._fds["session"], 4096)
        except OSError as error:
            raise SpoolError(fs_code(error, "state_read_failed")) from error
        if raw is None:
            return SessionState()
        try:
            return decode_state(raw)
        except ValueError as error:
            raise CorruptError("state_corrupt") from error

    def save_state(self, state: SessionState) -> None:
        try:
            write_atomic(STATE, self._fds["session"], encode_state(state))
        except OSError as error:
            raise SpoolError(fs_code(error, "state_write_failed")) from error

    @contextlib.contextmanager
    def worker_lock(self) -> Iterator[None]:
        """Block on the permanent lock; the kernel releases it if the owner dies."""
        fd = self._fds[WORKER_LOCK]
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
        except OSError as error:
            raise SpoolError("worker_lock_failed") from error
        self._locked = True
        try:
            with contextlib.suppress(OSError):
                os.ftruncate(fd, 0)
                os.pwrite(fd, f"{os.getpid()}\n".encode(), 0)
            yield
        finally:
            self._locked = False
            fcntl.flock(fd, fcntl.LOCK_UN)

    def append_log(self, error: DiagnosticError) -> None:
        """Keep the newest LOG_LIMIT bytes; only the lock holder may write."""
        if not self._locked:
            raise RuntimeError("append_log requires the worker lock")
        line = diagnostic_line(error.code, error).encode()
        session = self._fds["session"]
        try:
            try:
                fd = open_checked(LOG, session, os.O_RDONLY, stat.S_IFREG)
            except FileNotFoundError:
                existing = b""
            else:
                with os.fdopen(fd, "rb") as file:
                    size = os.fstat(file.fileno()).st_size
                    existing = os.pread(file.fileno(), LOG_LIMIT, max(0, size - LOG_LIMIT))
            data = existing + line
            if len(data) > LOG_LIMIT:
                data = data[-LOG_LIMIT:]
                data = data[data.find(b"\n") + 1:]
            write_atomic(LOG, session, data)
        except OSError as error:
            raise SpoolError(fs_code(error, "log_write_failed")) from error
