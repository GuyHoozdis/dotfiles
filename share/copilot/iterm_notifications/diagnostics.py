"""Payload-free diagnostic codes shared by the hook producer and the worker."""

import json
import os
import re
from datetime import UTC, datetime


_CODE = re.compile(r"[a-z][a-z0-9_]{0,63}")
_CLASS = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}")


class DiagnosticError(Exception):
    """Failure identified only by a bounded code and its cause's class name."""

    def __init__(self, code: str) -> None:
        if not _CODE.fullmatch(code):
            raise ValueError("invalid diagnostic code")
        self.code = code
        super().__init__(code)


def diagnostic_line(code: str, error: BaseException) -> str:
    """Format one JSON line that never includes messages, input, or arguments."""
    if not _CODE.fullmatch(code):
        raise ValueError("invalid diagnostic code")
    cause = error.__cause__ or error
    name = type(cause).__name__
    entry = {
        "code": code,
        "error": name if _CLASS.fullmatch(name) else "Exception",
        "pid": os.getpid(),
        "time": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    return json.dumps(entry, sort_keys=True) + "\n"
