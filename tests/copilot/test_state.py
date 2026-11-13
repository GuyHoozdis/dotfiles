import dataclasses
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "share" / "copilot"))

from iterm_notifications.context import HookEvent
from iterm_notifications.state import FeedbackState, reduce_event


SESSION_ID = "12345678-1234-1234-1234-123456789abc"


class FeedbackStateTests(unittest.TestCase):
    def event(self, name, notification_type=None):
        return HookEvent(name, None, notification_type, SESSION_ID)

    def test_transition_table_retains_independent_flags(self):
        for waiting in (False, True):
            for done in (False, True):
                original = FeedbackState(waiting, done)
                cases = [
                    ("SessionStart", None, FeedbackState(), None),
                    ("SessionEnd", None, FeedbackState(), None),
                    ("UserPromptSubmit", None, FeedbackState(), None),
                    ("PreToolUse", None, FeedbackState(), None),
                    ("PostToolUse", None, FeedbackState(), None),
                    ("Stop", None, FeedbackState(waiting, True), None if done else "done"),
                    ("Notification", "permission_prompt", FeedbackState(True, done),
                     None if waiting else "waiting"),
                    ("Notification", "elicitation_dialog", FeedbackState(True, done),
                     None if waiting else "waiting"),
                    ("Notification", "other", original, None),
                    ("Notification", None, original, None),
                ]
                for name, kind, expected, action in cases:
                    with self.subTest(waiting=waiting, done=done, name=name, kind=kind):
                        self.assertEqual(
                            reduce_event(original, self.event(name, kind)), (expected, action)
                        )
                        self.assertEqual(original, FeedbackState(waiting, done))

    def test_interleavings_deduplicate_until_activity(self):
        cases = [
            (["Notification", "Stop", "Notification"], ["waiting", "done", None]),
            (["Notification", "PreToolUse", "Notification"], ["waiting", None, "waiting"]),
            (["Stop", "Stop", "UserPromptSubmit", "Stop"], ["done", None, None, "done"]),
            (["Notification", "SessionEnd", "SessionStart", "Notification"],
             ["waiting", None, None, "waiting"]),
        ]
        for names, expected in cases:
            with self.subTest(names=names):
                state = FeedbackState()
                actions = []
                for name in names:
                    state, action = reduce_event(state, self.event(name, "permission_prompt"))
                    actions.append(action)
                self.assertEqual(actions, expected)

    def test_state_is_immutable(self):
        state = FeedbackState()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            state.waiting_seen = True


if __name__ == "__main__":
    unittest.main()
