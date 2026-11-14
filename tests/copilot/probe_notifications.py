#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["iterm2"]
# ///

"""Explicit, operator-controlled iTerm2 notification transport probe."""

import argparse
import contextlib
import io
import json
import os
import signal
import stat
import sys
import uuid
from collections.abc import Sequence
from importlib.metadata import version


PROFILE_GUID = "870214EA-844A-4654-A241-B7EB0B766076"
PROFILE_KEYS = (
    "BM Growl",
    "Send Terminal Generated Alerts",
    "Send Bell Alert",
    "Send Idle Alert",
    "Send New Output Alert",
    "Send Session Ended Alert",
    "Suppress Alerts in Active Session",
    "Send Alerts To Companion",
    "Silence Bell",
)
PAYLOADS = {
    "waiting": b"\x1b]9;Copilot test: waiting for input\x07",
    "done": b"\x07",
}


class ProbeError(Exception):
    """An expected, sanitized probe failure."""


class ProbeTimeout(BaseException):
    """The overall operation deadline expired."""


def parse_uuid(value: str) -> str:
    try:
        return str(uuid.UUID(value)).upper()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("session must be a UUID") from exc


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True, type=parse_uuid, help="exact source session UUID")
    parser.add_argument("--inspect", action="store_true", help="read source and profile baseline only")
    parser.add_argument("--transport", choices=("tty", "api"))
    parser.add_argument("--kind", choices=("waiting", "done"))
    args = parser.parse_args(argv)
    if args.inspect:
        if args.transport or args.kind:
            parser.error("--inspect cannot be combined with --transport or --kind")
    elif not args.transport or not args.kind:
        parser.error("notification requires both --transport and --kind")
    return args


def validate_tty_path(path: object) -> str:
    if (
        not isinstance(path, str)
        or not path.startswith("/dev/")
        or os.path.normpath(path) != path
        or os.path.realpath(path) != path
        or not path.isprintable()
    ):
        raise ProbeError("source tty is not a direct device path under /dev")
    return path


def write_tty(path: object, data: bytes) -> None:
    path = validate_tty_path(path)
    try:
        before = os.lstat(path)
        if not stat.S_ISCHR(before.st_mode) or before.st_uid != os.getuid():
            raise ProbeError("source tty is not a user-owned character device")
        fd = os.open(path, os.O_WRONLY | os.O_NONBLOCK | os.O_NOCTTY | os.O_NOFOLLOW)
        try:
            opened = os.fstat(fd)
            after = os.lstat(path)
            if (
                not stat.S_ISCHR(opened.st_mode)
                or opened.st_uid != os.getuid()
                or device_identity(before) != device_identity(opened)
                or device_identity(after) != device_identity(opened)
                or not os.isatty(fd)
            ):
                raise ProbeError("source tty descriptor validation failed")
            if os.write(fd, data) != len(data):
                raise ProbeError("tty write was incomplete; delivery is unknown")
        finally:
            os.close(fd)
    except OSError as exc:
        raise ProbeError("source tty could not be validated or written; delivery may be unknown") from exc


def device_identity(entry: os.stat_result) -> tuple[int, int, int]:
    return entry.st_dev, entry.st_ino, entry.st_rdev


def source_location(app: object, session_id: str) -> dict[str, str | None]:
    for window in app.windows:
        for tab in window.tabs:
            for session in tab.sessions:
                if session.session_id == session_id:
                    return {"window_id": window.window_id, "tab_id": tab.tab_id}
    return {"window_id": None, "tab_id": None}


async def probe(connection: object, args: argparse.Namespace, iterm2: object) -> dict[str, object]:
    app = await iterm2.async_get_app(connection)
    if app is None:
        raise ProbeError("iTerm application is unavailable")
    session = app.get_session_by_id(args.session, include_buried=False)
    if session is None:
        session = app.get_session_by_id(args.session.lower(), include_buried=False)
    if session is None or session.session_id.upper() != args.session:
        raise ProbeError("exact visible source session was not found")
    profile = await session.async_get_profile()
    if (profile.original_guid or profile.guid) != PROFILE_GUID:
        raise ProbeError("source session does not use the Copilot Agents profile")
    tty = await session.async_get_variable("tty")
    try:
        tty_path = validate_tty_path(tty)
    except ProbeError:
        tty_path = None
    result = {
        "session_id": session.session_id,
        **source_location(app, session.session_id),
        "profile_guid": profile.guid,
        "original_profile_guid": profile.original_guid,
        "tty": tty_path,
        "iterm2_api_version": version("iterm2"),
    }
    if args.inspect:
        properties = profile.all_properties
        result["baseline"] = {
            key: properties[key] if type(properties.get(key)) in (bool, int) else None for key in PROFILE_KEYS
        }
        result["baseline_unavailable"] = [key for key, value in result["baseline"].items() if value is None]
        result["status"] = "inspection_only"
    else:
        if args.transport == "tty":
            write_tty(tty, PAYLOADS[args.kind])
        else:
            await session.async_inject(PAYLOADS[args.kind])
        result.update(status="submitted_not_verified", transport=args.transport, kind=args.kind)
    return result


def deadline_expired(signum: int, frame: object) -> None:
    raise ProbeTimeout()


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    import iterm2
    import websockets.exceptions

    async def run(connection: object) -> dict[str, object]:
        try:
            return await probe(connection, args, iterm2)
        except ProbeError as exc:
            return {"error": str(exc)}
        except iterm2.RPCException:
            return {"error": "iTerm API request failed; delivery may be unknown"}
        except OSError:
            return {"error": "iTerm API I/O failed; delivery may be unknown"}

    previous = signal.signal(signal.SIGALRM, deadline_expired)
    signal.alarm(15)
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = iterm2.run_until_complete(run)
    except ProbeTimeout:
        result = {"error": "operation timed out; delivery may be unknown"}
    except (SystemExit, OSError, websockets.exceptions.WebSocketException):
        result = {"error": "iTerm API failed; check API availability and authorization; delivery may be unknown"}
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)
    if not isinstance(result, dict):
        result = {"error": "iTerm API returned no result"}
    print(json.dumps(result, sort_keys=True), file=sys.stderr if "error" in result else sys.stdout)
    return 1 if "error" in result else 0


if __name__ == "__main__":
    sys.exit(main())
