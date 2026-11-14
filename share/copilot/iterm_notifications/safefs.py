"""Owner-only, no-follow file primitives relative to validated directory fds."""

import contextlib
import errno
import os
import secrets
import stat

from .diagnostics import DiagnosticError


UNSAFE = frozenset({errno.ELOOP, errno.ENOTDIR, errno.EMLINK})
NOFOLLOW = os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK


class SpoolError(DiagnosticError):
    """Unsafe or unavailable notification spool state."""


class CorruptError(SpoolError):
    """Published content that will never become valid; diagnose and discard."""


def fs_code(error: OSError, default: str) -> str:
    return "spool_unsafe" if error.errno in UNSAFE else default


def _validate(fd: int, kind: int) -> None:
    status = os.fstat(fd)
    if stat.S_IFMT(status.st_mode) != kind or status.st_uid != os.geteuid():
        raise SpoolError("spool_unsafe")
    if kind == stat.S_IFREG and status.st_nlink != 1:
        raise SpoolError("spool_unsafe")
    if status.st_mode & 0o077:
        os.fchmod(fd, 0o700 if kind == stat.S_IFDIR else 0o600)


def open_checked(name: str, dir_fd: int, flags: int, kind: int) -> int:
    fd = os.open(name, flags | NOFOLLOW, 0o600, dir_fd=dir_fd)
    with contextlib.ExitStack() as cleanup:
        cleanup.callback(os.close, fd)
        _validate(fd, kind)
        cleanup.pop_all()
    return fd


def open_file(name: str, dir_fd: int) -> int:
    """Create-or-open; APFS can fail concurrent non-exclusive O_CREAT with ENOENT."""
    try:
        return open_checked(name, dir_fd, os.O_RDWR | os.O_CREAT | os.O_EXCL, stat.S_IFREG)
    except FileExistsError:
        return open_checked(name, dir_fd, os.O_RDWR, stat.S_IFREG)


def open_dir(name: str, dir_fd: int) -> int:
    with contextlib.suppress(FileExistsError):
        os.mkdir(name, 0o700, dir_fd=dir_fd)
    return open_checked(name, dir_fd, os.O_RDONLY | os.O_DIRECTORY, stat.S_IFDIR)


def read_small(name: str, dir_fd: int, limit: int) -> bytes | None:
    try:
        fd = open_checked(name, dir_fd, os.O_RDONLY, stat.S_IFREG)
    except FileNotFoundError:
        return None
    with os.fdopen(fd, "rb") as file:
        return file.read(limit + 1)


def write_atomic(name: str, dir_fd: int, data: bytes) -> None:
    temp = f".{name}.{os.getpid()}.{secrets.token_hex(4)}.tmp"
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | NOFOLLOW, 0o600, dir_fd=dir_fd)
    published = False
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp, name, src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
        published = True
    finally:
        if not published:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(temp, dir_fd=dir_fd)
