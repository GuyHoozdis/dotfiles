"""Ephemeral terminal helper: owns the iTerm2 connection for one worker drain."""

import os
import signal
import sys
import threading

from .diagnostics import DiagnosticError
from .ipc import MAX_LINE, MessageKind, decode_request, encode_message
from .worker import DeliveryError


def watch_lifeline(fd: int) -> None:
    """Kill this helper's process group once the parent's lifeline write end closes."""
    if os.getpgrp() != os.getpid():
        os.setpgid(0, 0)

    def watch() -> None:
        try:
            os.read(fd, 1)
        except OSError:
            pass
        os.killpg(os.getpgrp(), signal.SIGKILL)

    threading.Thread(target=watch, name="lifeline", daemon=True).start()


def main(lifeline: int) -> int:
    watch_lifeline(lifeline)
    protocol = os.fdopen(os.dup(1), "wb", buffering=0)
    quiet = os.open(os.devnull, os.O_WRONLY)
    os.dup2(quiet, 1)
    os.dup2(quiet, 2)
    os.close(quiet)

    def send(kind: MessageKind, error: DiagnosticError | None = None) -> None:
        protocol.write(encode_message(kind, error))

    def report(error: DiagnosticError) -> None:
        send("diagnostic", error)

    from .terminal import open_sink

    context = open_sink(report=report)
    try:
        sink = context.__enter__()
    except DeliveryError as error:
        send("failed", error)
        return 0
    send("ready")
    try:
        while line := sys.stdin.buffer.readline(MAX_LINE + 1):
            try:
                if not line.endswith(b"\n"):
                    raise DeliveryError("terminal_helper_protocol")
                action, event = decode_request(line)
                sink(action, event)
            except DeliveryError as error:
                send("failed", error)
                if error.code == "terminal_helper_protocol":
                    return 1
                continue
            send("done")
    finally:
        context.__exit__(None, None, None)
    return 0
