"""Hook producer and private worker entry; stdout is never written in hook mode."""

import argparse
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from .context import MAX_INPUT_BYTES, ContextError, parse_event
from .diagnostics import DiagnosticError, diagnostic_line
from .spool import Spool, SpoolError
from .worker import SinkFactory, drain, open_unavailable_sink


ENTRY = Path(__file__).resolve().parents[3] / "bin" / "copilot-iterm-notify.py"


@dataclass(frozen=True, slots=True)
class WorkerLauncher:
    python: str
    entry: Path

    def launch(self, source_uuid: str) -> None:
        """Start a detached worker without inheriting hook pipes or waiting on it."""
        subprocess.Popen(
            [self.python, str(self.entry), "--worker", source_uuid],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True, close_fds=True,
        )


DEFAULT_LAUNCHER = WorkerLauncher(sys.executable, ENTRY)


def _stderr(code: str, error: BaseException) -> None:
    sys.stderr.write(diagnostic_line(code, error))
    sys.stderr.flush()


def _discard(stream: BinaryIO) -> None:
    remaining = MAX_INPUT_BYTES + 1
    try:
        while remaining > 0 and (chunk := stream.read(min(remaining, 65536))):
            remaining -= len(chunk)
    except (OSError, ValueError):
        return


def run_hook(
    event: str, stream: BinaryIO, environ: Mapping[str, str],
    launcher: WorkerLauncher = DEFAULT_LAUNCHER,
) -> int:
    """Publish one sanitized event; every handled failure still returns 0."""
    if not environ.get("ITERM_SESSION_ID") or environ.get("TMUX"):
        _discard(stream)
        return 0
    try:
        hook_event = parse_event(event, stream, environ)
    except ContextError as error:
        _stderr(error.code, error)
        return 0
    try:
        with Spool.open(hook_event.source_uuid, environ) as spool:
            spool.enqueue(hook_event)
    except SpoolError as error:
        _stderr(error.code, error)
        return 0
    try:
        launcher.launch(hook_event.source_uuid)
    except (OSError, subprocess.SubprocessError) as error:
        _stderr("worker_launch_failed", error)
    return 0


def run_worker(
    source_uuid: str, environ: Mapping[str, str],
    open_sink: SinkFactory = open_unavailable_sink,
) -> int:
    try:
        spool = Spool.open(source_uuid, environ)
    except SpoolError as error:
        _stderr(error.code, error)
        return 1
    with spool:
        def report(error: DiagnosticError) -> None:
            _stderr(error.code, error)
            try:
                spool.append_log(error)
            except SpoolError as log_error:
                _stderr(log_error.code, log_error)

        try:
            return 0 if drain(spool, open_sink, report) else 1
        except SpoolError as error:
            _stderr(error.code, error)
            return 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="copilot-iterm-notify.py",
        description="Queue a Copilot hook event for its originating iTerm2 session.",
    )
    parser.add_argument("event", nargs="?", help="Copilot hook lifecycle event name")
    parser.add_argument("--worker", metavar="UUID", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if (args.event is None) == (args.worker is None):
        parser.error("expected exactly one EVENT")
    if args.worker is not None:
        return run_worker(args.worker, os.environ)
    return run_hook(args.event, sys.stdin.buffer, os.environ)
