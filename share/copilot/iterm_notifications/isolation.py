"""Run iTerm2 delivery in an owned, killable helper process group."""

import os
import signal
import subprocess
import time
from collections.abc import Sequence
from contextlib import AbstractContextManager
from functools import cache
from types import TracebackType

from .context import HookEvent
from .diagnostics import DiagnosticError
from .ipc import LineReader, Message, decode_message, encode_request, write_all
from .worker import Action, DeliveryError, FeedbackSink, Reporter


ACTION_TIMEOUT = 15.0
CLOSE_GRACE = 2.0


class RemoteDeliveryError(DeliveryError):
    """A helper-reported delivery failure; the helper itself remains usable."""


@cache
def _remote_cause(name: str) -> type[Exception]:
    return type(name, (Exception,), {})


def _remote(error_type: type[DiagnosticError], message: Message) -> DiagnosticError:
    error = error_type(message.code or "terminal_helper_protocol")
    error.__cause__ = _remote_cause(message.error)()
    return error


class _Helper:
    def __init__(self, command: Sequence[str], report: Reporter) -> None:
        self._report = report
        lifeline, self._lifeline = os.pipe()
        try:
            self._process = subprocess.Popen(
                [*command, str(lifeline)],
                bufsize=0,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                pass_fds=(lifeline,),
            )
        except (OSError, subprocess.SubprocessError) as error:
            os.close(self._lifeline)
            raise DeliveryError("terminal_helper_spawn_failed") from error
        finally:
            os.close(lifeline)
        stdin, stdout = self._process.stdin, self._process.stdout
        if stdin is None or stdout is None:
            raise RuntimeError("helper pipes were not created")
        self._stdin, self._stdout = stdin, stdout
        os.set_blocking(self._stdin.fileno(), False)
        os.set_blocking(self._stdout.fileno(), False)
        self._reader = LineReader(self._stdout.fileno())
        try:
            self._await("ready", time.monotonic() + ACTION_TIMEOUT)
        except DeliveryError:
            self.kill()
            raise

    def _await(self, kind: str, deadline: float) -> None:
        while (line := self._reader.read_line(deadline)) is not None:
            message = decode_message(line)
            if message.kind == "diagnostic":
                self._report(_remote(DiagnosticError, message))
            elif message.kind == "failed":
                raise _remote(RemoteDeliveryError, message)
            elif message.kind == kind:
                return
            else:
                raise DeliveryError("terminal_helper_protocol")
        raise DeliveryError("terminal_helper_exited")

    def deliver(self, action: Action, event: HookEvent) -> None:
        deadline = time.monotonic() + ACTION_TIMEOUT
        try:
            write_all(self._stdin.fileno(), encode_request(action, event), deadline)
            self._await("done", deadline)
        except RemoteDeliveryError:
            raise
        except DeliveryError:
            self.kill()
            raise

    def close(self) -> None:
        """Request a graceful exit, then always kill the group before reaping."""
        try:
            self._stdin.close()
            deadline = time.monotonic() + CLOSE_GRACE
            try:
                while (line := self._reader.read_line(deadline)) is not None:
                    message = decode_message(line)
                    if message.kind != "diagnostic":
                        raise DeliveryError("terminal_helper_protocol")
                    self._report(_remote(DiagnosticError, message))
            except DeliveryError as error:
                if error.code == "terminal_helper_timeout":
                    error = DeliveryError("terminal_helper_close_timeout")
                self._report(error)
        finally:
            self.kill()

    def kill(self) -> None:
        # The unreaped leader keeps its PID, so the group ID cannot be reused yet.
        try:
            os.killpg(self._process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        os.close(self._lifeline)
        self._stdin.close()
        self._stdout.close()
        self._process.wait()


class _IsolatedSink(AbstractContextManager[FeedbackSink]):
    def __init__(self, command: Sequence[str], report: Reporter) -> None:
        self._command = tuple(command)
        self._report = report
        self._helper: _Helper | None = None

    def __enter__(self) -> FeedbackSink:
        return self._deliver

    def _deliver(self, action: Action, event: HookEvent) -> None:
        if self._helper is None:
            self._helper = _Helper(self._command, self._report)
        try:
            self._helper.deliver(action, event)
        except RemoteDeliveryError:
            raise
        except DeliveryError:
            # A later action may start a replacement; this one is never retried.
            self._helper = None
            raise

    def __exit__(
        self,
        _kind: type[BaseException] | None,
        _value: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        helper, self._helper = self._helper, None
        if helper is not None:
            helper.close()


def open_sink(*, report: Reporter, command: Sequence[str]) -> AbstractContextManager[FeedbackSink]:
    """Deliver through one helper per drain; the lifeline FD is appended to command."""
    return _IsolatedSink(command, report)
