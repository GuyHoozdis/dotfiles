"""Pure lifecycle transitions and state encoding; files belong to the spool."""

import json
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


@dataclass(frozen=True, slots=True)
class SessionState:
    feedback: FeedbackState = FeedbackState()
    last_seq: int = 0


def apply_record(
    state: SessionState, seq: int, event: HookEvent,
) -> tuple[SessionState, FeedbackAction]:
    """Ignore replayed sequences so a crash before queue removal never repeats."""
    if seq <= state.last_seq:
        return state, None
    feedback, action = reduce_event(state.feedback, event)
    return SessionState(feedback, seq), action


_STATE_KEYS = frozenset({"version", "last_seq", "waiting_seen", "done_seen"})


def encode_state(state: SessionState) -> bytes:
    return json.dumps({
        "version": 1,
        "last_seq": state.last_seq,
        "waiting_seen": state.feedback.waiting_seen,
        "done_seen": state.feedback.done_seen,
    }, sort_keys=True).encode() + b"\n"


def decode_state(raw: bytes) -> SessionState:
    """Raises ValueError for anything other than a current, well-typed state."""
    payload = json.loads(raw)
    if not isinstance(payload, dict) or set(payload) != _STATE_KEYS or payload["version"] != 1:
        raise ValueError("invalid_state")
    last_seq = payload["last_seq"]
    flags = (payload["waiting_seen"], payload["done_seen"])
    if type(last_seq) is not int or last_seq < 0 or not all(type(f) is bool for f in flags):
        raise ValueError("invalid_state")
    return SessionState(FeedbackState(*flags), last_seq)
