"""Serialized per-session drain; terminal delivery is an injected sink."""

import contextlib
from collections.abc import Callable
from contextlib import AbstractContextManager
from types import TracebackType
from typing import Literal, Protocol

from .context import HookEvent
from .diagnostics import DiagnosticError
from .spool import CorruptError, Spool, SpoolError
from .state import SessionState, apply_record


Action = Literal["waiting", "done"]


class DeliveryError(DiagnosticError):
    """Raised by sinks for known terminal/API failures; never retried."""


class FeedbackSink(Protocol):
    def __call__(self, action: Action, event: HookEvent) -> None: ...


type SinkFactory = Callable[[], AbstractContextManager[FeedbackSink]]
type Reporter = Callable[[DiagnosticError], None]


class _UnavailableSink(AbstractContextManager[FeedbackSink]):
    def __enter__(self) -> FeedbackSink:
        raise DeliveryError("terminal_adapter_unavailable")

    def __exit__(
        self, kind: type[BaseException] | None, value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


def open_unavailable_sink() -> AbstractContextManager[FeedbackSink]:
    """Placeholder until the terminal adapter exists; never claims delivery."""
    return _UnavailableSink()


def _load(spool: Spool, report: Reporter) -> SessionState:
    try:
        return spool.load_state()
    except CorruptError as error:
        report(error)
        return SessionState()


def _drain_locked(
    spool: Spool, open_sink: SinkFactory, report: Reporter, sinks: contextlib.ExitStack,
) -> None:
    sink: FeedbackSink | None = None
    state = _load(spool, report)
    while seqs := spool.pending():
        for seq in seqs:
            if seq <= state.last_seq:
                spool.remove_record(seq)
                continue
            try:
                event = spool.read_record(seq)
            except CorruptError as error:
                report(error)
                state = SessionState(state.feedback, seq)
                spool.save_state(state)
                spool.remove_record(seq)
                continue
            state, action = apply_record(state, seq, event)
            spool.save_state(state)
            if action is not None:
                try:
                    if sink is None:
                        sink = sinks.enter_context(open_sink())
                    sink(action, event)
                except DeliveryError as error:
                    report(error)
            spool.remove_record(seq)


def drain(spool: Spool, open_sink: SinkFactory, report: Reporter) -> bool:
    """Drain every queued record in sequence order under the worker lock.

    Observed state is persisted before each action, so delivery is at most once:
    a crash after persisting but before delivery loses that alert.
    The sink opens lazily on the first action and closes before the lock is released.
    Returns False after reporting a spool failure that stopped the drain.
    """
    with spool.worker_lock():
        try:
            with contextlib.ExitStack() as sinks:
                _drain_locked(spool, open_sink, report, sinks)
        except DeliveryError as error:
            report(error)
        except SpoolError as error:
            report(error)
            return False
    return True
