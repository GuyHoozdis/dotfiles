"""Verified direct writes to the originating iTerm2 session's tty."""

import os
import select
import stat
import time
from pathlib import Path

from .worker import DeliveryError


WRITE_TIMEOUT = 15.0


def write_tty(tty: str, data: bytes) -> None:
    """Write all bytes to an owned character-device tty directly under /dev."""
    path = Path(tty)
    if path.parent != Path("/dev") or path.name in ("", ".", ".."):
        raise DeliveryError("tty_unsafe")
    descriptor: int | None = None
    try:
        before = os.lstat(path)
        if stat.S_ISLNK(before.st_mode) or not stat.S_ISCHR(before.st_mode):
            raise DeliveryError("tty_unsafe")
        if before.st_uid != os.getuid():
            raise DeliveryError("tty_unsafe")
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
        opened = os.fstat(descriptor)
        after = os.lstat(path)
        if (
            not stat.S_ISCHR(opened.st_mode)
            or opened.st_uid != os.getuid()
            or not os.isatty(descriptor)
            or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)
            or (opened.st_dev, opened.st_ino) != (after.st_dev, after.st_ino)
        ):
            raise DeliveryError("tty_unsafe")
        deadline = time.monotonic() + WRITE_TIMEOUT
        offset = 0
        poller = select.poll()
        poller.register(descriptor, select.POLLOUT)
        while offset < len(data):
            if time.monotonic() >= deadline:
                raise DeliveryError("tty_write_timeout")
            try:
                offset += os.write(descriptor, data[offset:])
            except BlockingIOError:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not poller.poll(int(remaining * 1000)):
                    raise DeliveryError("tty_write_timeout")
    except DeliveryError:
        raise
    except OSError as error:
        raise DeliveryError("tty_write_failed") from error
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError as error:
                raise DeliveryError("tty_close_failed") from error
