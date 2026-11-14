"""Hard wall-clock deadline and output isolation around iTerm2 library calls."""

from __future__ import annotations

import contextlib
import os
import signal
import threading
import time
from collections.abc import Iterator
from types import FrameType


class HardTimeout(TimeoutError):
    """The wall-clock deadline expired, possibly inside synchronous library code."""


def _expire(_signum: int, _frame: FrameType | None) -> None:
    raise HardTimeout


@contextlib.contextmanager
def guarded_call(seconds: float) -> Iterator[None]:
    """Bound a call with SIGALRM and discard any raw library stdout/stderr."""
    if threading.current_thread() is not threading.main_thread():
        raise HardTimeout
    previous_handler = signal.signal(signal.SIGALRM, _expire)
    previous_delay, previous_interval = signal.setitimer(signal.ITIMER_REAL, seconds)
    started = time.monotonic()
    try:
        with open(os.devnull, "w", encoding="utf-8") as sink:
            with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                yield
    finally:
        try:
            signal.setitimer(signal.ITIMER_REAL, 0)
        finally:
            signal.signal(signal.SIGALRM, previous_handler)
            if previous_delay > 0:
                remaining = max(previous_delay - (time.monotonic() - started), 1e-6)
                signal.setitimer(signal.ITIMER_REAL, remaining, previous_interval)
