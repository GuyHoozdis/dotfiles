"""Pure lifecycle transitions; persistence belongs to the worker boundary."""

from dataclasses import dataclass
from typing import Literal

from .context import HookEvent, WAITING_TYPES


FeedbackAction = Literal["waiting", "done"] | None


@dataclass(frozen=True, slots=True)
class FeedbackState:
    waiting_seen: bool = False
    done_seen: bool = False


def reduce_event(
    state: FeedbackState, event: HookEvent,
) -> tuple[FeedbackState, FeedbackAction]:
    """Deduplicate feedback until lifecycle activity resets both flags."""
    if event.event in {
        "SessionStart", "SessionEnd", "UserPromptSubmit", "PreToolUse", "PostToolUse",
    }:
        return FeedbackState(), None
    if event.event == "Notification" and event.notification_type in WAITING_TYPES:
        if not state.waiting_seen:
            return FeedbackState(True, state.done_seen), "waiting"
    if event.event == "Stop" and not state.done_seen:
        return FeedbackState(state.waiting_seen, True), "done"
    return state, None
