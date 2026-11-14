"""Safe hook input and originating-session context; no terminal dependencies."""

import json
import os
import re
import stat
import subprocess
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO


MAX_INPUT_BYTES = 10 * 1024 * 1024
EVENT_NAMES = frozenset(
    {
        "SessionStart",
        "UserPromptSubmit",
        "PreToolUse",
        "PostToolUse",
        "Notification",
        "Stop",
        "SessionEnd",
    }
)
WAITING_TYPES = frozenset({"permission_prompt", "elicitation_dialog"})
_SESSION_ID = re.compile(r"(?:w[^:\s]+:)?([0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})")


class ContextError(Exception):
    """Bounded diagnostic code, safe for orchestration logs."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class HookEvent:
    event: str
    cwd: str | None
    notification_type: str | None
    source_uuid: str


@dataclass(frozen=True, slots=True)
class SourceContext:
    label: str | None
    branch: str | None


def _reject_constant(value: str) -> None:
    raise ValueError("nonfinite_json_number")


def parse_event(event: str, stream: BinaryIO, environ: Mapping[str, str]) -> HookEvent:
    """Read bounded hook JSON and retain only routing and lifecycle fields.

    Args:
        event: Lifecycle name supplied by the hook invocation.
        stream: Binary hook input.
        environ: Originating hook environment, not the focused pane.

    Raises:
        ContextError: Invalid input or an unavailable input stream.
    """
    if event not in EVENT_NAMES:
        raise ContextError("invalid_event")
    match = _SESSION_ID.fullmatch(environ.get("ITERM_SESSION_ID", ""))
    if match is None:
        raise ContextError("invalid_source_uuid")
    source_uuid = str(uuid.UUID(match.group(1)))
    raw = bytearray()
    read_failed = False
    try:
        while len(raw) <= MAX_INPUT_BYTES:
            chunk = stream.read(MAX_INPUT_BYTES + 1 - len(raw))
            if not chunk:
                break
            raw.extend(chunk)
    except (OSError, ValueError):
        read_failed = True
    if read_failed:
        raise ContextError("input_read_failed")
    if len(raw) > MAX_INPUT_BYTES:
        raise ContextError("input_too_large")
    invalid_json = False
    payload: object = None
    try:
        payload = json.loads(raw, parse_constant=_reject_constant)
    except (ValueError, UnicodeDecodeError, RecursionError):
        invalid_json = True
    if invalid_json:
        raise ContextError("invalid_json")
    if not isinstance(payload, dict):
        raise ContextError("invalid_payload")
    cwd = payload.get("cwd")
    notification_type = payload.get("notification_type")
    if cwd is not None and not isinstance(cwd, str):
        raise ContextError("invalid_field")
    if notification_type is not None and not isinstance(notification_type, str):
        raise ContextError("invalid_field")
    return HookEvent(event, cwd, notification_type, source_uuid)


def _git(
    cwd: str,
    args: list[str],
    deadline: float,
    allowed: tuple[int, ...] = (),
) -> subprocess.CompletedProcess[str]:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ContextError("git_timeout")
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("GIT_") or key == "GIT_CEILING_DIRECTORIES"
    }
    env["LC_ALL"] = "C"
    result: subprocess.CompletedProcess[str] | None = None
    error: str | None = None
    try:
        result = subprocess.run(
            ["git", "-C", cwd, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="surrogateescape",
            timeout=remaining,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired:
        error = "git_timeout"
    except OSError:
        error = "git_execution_failed"
    if error is not None:
        raise ContextError(error)
    assert result is not None
    if result.returncode != 0 and result.returncode not in allowed:
        raise ContextError("git_failed")
    return result


def resolve_context(event: HookEvent, repo_label: str | None = None) -> SourceContext:
    """Resolve source Git context with a shared 15-second subprocess budget.

    Missing/unreadable directories and non-Git directories have no Git context.
    Unexpected filesystem and Git failures raise ContextError.
    """
    label = repo_label if repo_label and repo_label.strip() else None
    if not event.cwd:
        return SourceContext(label, None)
    status: os.stat_result | None = None
    error: str | None = None
    try:
        status = os.stat(event.cwd)
    except (FileNotFoundError, NotADirectoryError, PermissionError):
        pass
    except (OSError, ValueError):
        error = "cwd_unavailable"
    if error:
        raise ContextError(error)
    if status is None or not stat.S_ISDIR(status.st_mode) or not os.access(event.cwd, os.R_OK | os.X_OK):
        return SourceContext(label, None)
    deadline = time.monotonic() + 15
    top = _git(event.cwd, ["rev-parse", "--show-toplevel"], deadline, (128,))
    if top.returncode:
        if top.stderr.startswith("fatal: not a git repository"):
            return SourceContext(label, None)
        raise ContextError("git_failed")
    toplevel = Path(top.stdout.removesuffix("\n"))
    if label is None:
        common = Path(
            _git(
                event.cwd,
                [
                    "rev-parse",
                    "--path-format=absolute",
                    "--git-common-dir",
                ],
                deadline,
            ).stdout.removesuffix("\n")
        )
        git_dir = Path(
            _git(
                event.cwd,
                [
                    "rev-parse",
                    "--absolute-git-dir",
                ],
                deadline,
            ).stdout.removesuffix("\n")
        )
        label = f"{common.parent.name}|{toplevel.name}" if common != git_dir else toplevel.name
    symbolic = _git(event.cwd, ["symbolic-ref", "--quiet", "--short", "HEAD"], deadline, (1,))
    branch = symbolic.stdout.removesuffix("\n")
    if symbolic.returncode == 1:
        branch = _git(event.cwd, ["rev-parse", "--short", "HEAD"], deadline).stdout.removesuffix("\n")
    return SourceContext(label, branch or None)


def _printable(value: str | None) -> str:
    return "".join(char for char in value or "" if char.isprintable())


def format_waiting_message(event: HookEvent, source: SourceContext) -> str:
    """Build a bounded OSC-safe body without looking at the focused pane."""
    label = _printable(source.label)
    if not label.strip():
        label = _printable(Path(event.cwd).name if event.cwd else None)
    if not label.strip():
        label = _printable(event.source_uuid)
    branch = _printable(source.branch)
    context = f"{label} [{branch}]" if branch.strip() else label
    return "Copilot needs your attention: " + context[:240]
