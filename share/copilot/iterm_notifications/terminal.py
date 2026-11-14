"""Deliver bounded attention feedback to the explicitly identified source TTY."""

from collections.abc import Callable
from contextlib import AbstractContextManager
from types import TracebackType

from .context import ContextError, HookEvent, SourceContext, format_waiting_message, resolve_context
from .terminal_api import ItermBridge, Reporter
from .tty import write_tty
from .worker import Action, DeliveryError, FeedbackSink


class _TerminalContext(AbstractContextManager[FeedbackSink]):
    def __init__(
        self,
        writer: Callable[[str, bytes], None],
        report: Reporter | None,
    ) -> None:
        self._writer = writer
        self._reporter = report
        self._bridge: ItermBridge | None = None

    def __enter__(self) -> FeedbackSink:
        bridge = ItermBridge(self._reporter)
        bridge.__enter__()
        self._bridge = bridge
        return self._deliver

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._bridge is not None:
            self._bridge.__exit__(exc_type, exc_value, traceback)
            self._bridge = None

    def _deliver(self, action: Action, event: HookEvent) -> None:
        if self._bridge is None:
            raise RuntimeError("terminal context is not open")
        source = self._bridge.session(event.source_uuid)
        if source is None or not self._bridge.profile_allowed(source):
            return
        original_tty = self._bridge.variable(source, "tty")
        if not original_tty:
            raise DeliveryError("tty_unavailable")
        label = self._bridge.variable(source, "user.repoLabel")
        try:
            context = resolve_context(event, label)
        except ContextError as error:
            self._bridge.report(error.code, error)
            context = SourceContext(label, None)

        payload = b"\x07"
        if action == "waiting":
            body = format_waiting_message(event, context).encode("utf-8")
            payload = b"\x1b]9;" + body + b"\x07"
            if self._bridge.focused(source):
                return

        source = self._bridge.session(event.source_uuid)
        if source is None or not self._bridge.profile_allowed(source):
            self._bridge.report("source_changed")
            return
        tty = self._bridge.variable(source, "tty")
        if not tty:
            raise DeliveryError("tty_unavailable")
        if tty != original_tty:
            raise DeliveryError("source_changed")
        try:
            self._writer(tty, payload)
        except DeliveryError:
            raise
        except OSError as error:
            raise DeliveryError("tty_write_failed") from error


def open_sink(
    report: Reporter | None = None,
) -> AbstractContextManager[FeedbackSink]:
    """Create one lazy iTerm2 connection for a worker drain."""
    return _TerminalContext(write_tty, report)
