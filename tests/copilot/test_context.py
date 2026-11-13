import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "share" / "copilot"))

from iterm_notifications import context


SESSION_ID = "12345678-1234-1234-1234-123456789abc"


class EventTests(unittest.TestCase):
    def parse(self, event="Notification", payload=None, session=SESSION_ID):
        body = {"cwd": "/source", "notification_type": "permission_prompt"}
        if payload is not None:
            body = payload
        return context.parse_event(
            event, io.BytesIO(json.dumps(body).encode()), {"ITERM_SESSION_ID": session}
        )

    def test_known_events_retain_only_safe_fields(self):
        for name in (
            "SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse",
            "Notification", "Stop", "SessionEnd",
        ):
            with self.subTest(name=name):
                event = self.parse(name, {
                    "cwd": "/source", "notification_type": "permission_prompt",
                    "prompt": "private", "tool_input": {"secret": "private"},
                })
                self.assertEqual(event.event, name)
                self.assertEqual(event.cwd, "/source")
                self.assertEqual(event.notification_type, "permission_prompt")
                self.assertEqual(event.source_uuid, SESSION_ID)
                self.assertNotIn("private", repr(event))
                self.assertEqual(set(event.__dataclass_fields__), {
                    "event", "cwd", "notification_type", "source_uuid",
                })

    def test_source_uuid_accepts_iterm_prefix_and_normalizes_case(self):
        self.assertEqual(
            self.parse(session=f"w0t1p2:{SESSION_ID.upper()}").source_uuid, SESSION_ID
        )

    def test_rejects_bad_event_uuid_and_field_types(self):
        cases = [
            ("Unknown", {}, SESSION_ID, "invalid_event"),
            ("Stop", {}, "", "invalid_source_uuid"),
            ("Stop", {}, "arbitrary:" + SESSION_ID, "invalid_source_uuid"),
            ("Stop", {}, SESSION_ID.replace("-", ""), "invalid_source_uuid"),
            ("Stop", {}, SESSION_ID + "\n", "invalid_source_uuid"),
            ("Stop", {}, "w0:extra:" + SESSION_ID, "invalid_source_uuid"),
            ("Stop", {"cwd": 1}, SESSION_ID, "invalid_field"),
            ("Stop", {"notification_type": []}, SESSION_ID, "invalid_field"),
        ]
        for name, body, session, code in cases:
            with self.subTest(code=code, body=body):
                with self.assertRaises(context.ContextError) as raised:
                    self.parse(name, body, session)
                self.assertEqual(raised.exception.code, code)

    def test_missing_optional_fields_and_unrelated_notification_are_accepted(self):
        event = self.parse(payload={})
        self.assertIsNone(event.cwd)
        self.assertIsNone(event.notification_type)
        self.assertEqual(self.parse(payload={"notification_type": "other"}).notification_type, "other")

    def test_rejects_malformed_nonobject_and_oversized_input_without_echo(self):
        cases = [
            (b'{"prompt": "secret"', "invalid_json"),
            (b"\xff", "invalid_json"),
            (b"[]", "invalid_payload"),
            (b"null", "invalid_payload"),
            (b"true", "invalid_payload"),
            (b'{"x": NaN}', "invalid_json"),
            (b"[" * 2000, "invalid_json"),
            (b"secret" + b"x" * context.MAX_INPUT_BYTES, "input_too_large"),
        ]
        for body, code in cases:
            with self.subTest(code=code):
                stream = io.BytesIO(body)
                with self.assertRaises(context.ContextError) as raised:
                    context.parse_event("Stop", stream, {"ITERM_SESSION_ID": SESSION_ID})
                self.assertEqual(raised.exception.code, code)
                self.assertLessEqual(len(str(raised.exception)), 100)
                self.assertNotIn("secret", str(raised.exception))
                self.assertIsNone(raised.exception.__cause__)
                self.assertIsNone(raised.exception.__context__)
                self.assertLessEqual(stream.tell(), context.MAX_INPUT_BYTES + 1)

    def test_exact_input_limit_is_accepted(self):
        body = b"{}" + b" " * (context.MAX_INPUT_BYTES - 2)
        event = context.parse_event("Stop", io.BytesIO(body), {"ITERM_SESSION_ID": SESSION_ID})
        self.assertEqual(event.event, "Stop")

    def test_read_error_is_structured(self):
        stream = mock.Mock(spec=io.BufferedReader)
        stream.read.side_effect = OSError("private")
        with self.assertRaises(context.ContextError) as raised:
            context.parse_event("Stop", stream, {"ITERM_SESSION_ID": SESSION_ID})
        self.assertEqual(raised.exception.code, "input_read_failed")
        self.assertNotIn("private", str(raised.exception))

    def test_partial_reads_are_not_treated_as_eof(self):
        stream = mock.Mock(spec=io.BufferedReader)
        stream.read.side_effect = [b'{"cwd":', b' "/source"}', b""]
        event = context.parse_event("Stop", stream, {"ITERM_SESSION_ID": SESSION_ID})
        self.assertEqual(event.cwd, "/source")

    def test_closed_input_stream_has_a_structured_error(self):
        stream = io.BytesIO()
        stream.close()
        with self.assertRaises(context.ContextError) as raised:
            context.parse_event("Stop", stream, {"ITERM_SESSION_ID": SESSION_ID})
        self.assertEqual(raised.exception.code, "input_read_failed")


class SourceContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        environment = mock.patch.dict(os.environ, {"GIT_CEILING_DIRECTORIES": str(self.base)})
        environment.start()
        self.addCleanup(environment.stop)
        self.repo = self.base / "répo with spaces"
        self.repo.mkdir()
        self.git("init", "--quiet", "--initial-branch=feature/slash")

    def git(self, *args, cwd=None):
        return subprocess.run(
            ["git", "-C", str(cwd or self.repo), *args],
            check=True, capture_output=True, text=True, timeout=15,
        ).stdout.rstrip("\n")

    def commit(self):
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "--quiet", "--allow-empty", "-m", "fixture")

    def event(self, cwd=None):
        return context.HookEvent("Notification", str(cwd or self.repo), "permission_prompt", SESSION_ID)

    def message(self, event=None, repo_label=None):
        event = event or self.event()
        return context.format_waiting_message(event, context.resolve_context(event, repo_label))

    def test_regular_and_unborn_repository_with_slash_branch(self):
        expected = "Copilot needs your attention: répo with spaces [feature/slash]"
        self.assertEqual(self.message(), expected)
        self.commit()
        self.assertEqual(self.message(), expected)

    def test_detached_head_uses_abbreviated_commit(self):
        self.commit()
        sha = self.git("rev-parse", "--short", "HEAD")
        self.git("checkout", "--quiet", "--detach")
        self.assertEqual(self.message(), f"Copilot needs your attention: répo with spaces [{sha}]")

    def test_linked_worktree_uses_common_repository_inside_or_outside_dotworktrees(self):
        self.commit()
        for index, target in enumerate((
            self.base / "outside ü", self.repo / ".worktrees" / "inside ü",
        )):
            self.git("worktree", "add", "--quiet", "-b", f"topic/{index}", str(target))
            self.assertEqual(
                self.message(self.event(target)),
                f"Copilot needs your attention: répo with spaces|{target.name} [topic/{index}]",
            )
            nested = target / "nested"
            nested.mkdir()
            self.assertEqual(self.message(self.event(nested)), self.message(self.event(target)))

    def test_nonempty_source_repo_label_wins_without_focused_context(self):
        self.assertEqual(
            self.message(repo_label="source|label"),
            "Copilot needs your attention: source|label [feature/slash]",
        )
        self.assertEqual(self.message(repo_label="  "), self.message())

    def test_non_git_missing_and_unreadable_cwd_fallback(self):
        missing = self.base / "missing ü"
        non_git = self.base / "not a repo ü"
        non_git.mkdir()
        for path in (non_git, missing):
            with self.subTest(path=path):
                self.assertEqual(self.message(self.event(path)), f"Copilot needs your attention: {path.name}")
        with mock.patch.object(context.os, "stat", autospec=True, side_effect=PermissionError()):
            self.assertEqual(self.message(), "Copilot needs your attention: répo with spaces")
        event = context.HookEvent("Stop", None, None, SESSION_ID)
        self.assertEqual(self.message(event), f"Copilot needs your attention: {SESSION_ID}")
        self.assertEqual(self.message(event, "source"), "Copilot needs your attention: source")

    def test_context_controls_removed_and_printable_unicode_bounded(self):
        event = context.HookEvent("Notification", "/bad\x1b\x07\n\r\x85name", None, SESSION_ID)
        source = context.SourceContext("4;répo\x1b]9;evil\x07\n\r\x85", "branch\x00\x7f\x9f")
        message = context.format_waiting_message(event, source)
        self.assertEqual(message, "Copilot needs your attention: 4;répo]9;evil [branch]")
        long = context.format_waiting_message(event, context.SourceContext("é" * 300, None))
        self.assertEqual(long, "Copilot needs your attention: " + "é" * 240)
        fallback = context.format_waiting_message(event, context.SourceContext("\x07", "\x1b"))
        self.assertEqual(fallback, "Copilot needs your attention: badname")
        controls = "".join(chr(code) for code in (*range(32), *range(127, 160)))
        self.assertEqual(
            context.format_waiting_message(event, context.SourceContext("répo" + controls, None)),
            "Copilot needs your attention: répo",
        )

    def test_unreadable_directory_has_no_git_context(self):
        self.repo.chmod(0)
        try:
            self.assertEqual(self.message(), "Copilot needs your attention: répo with spaces")
        finally:
            self.repo.chmod(0o700)

    def test_inherited_git_path_overrides_cannot_select_another_source(self):
        with mock.patch.dict(os.environ, {
            "GIT_DIR": str(self.base / "other"), "GIT_WORK_TREE": str(self.base),
            "GIT_COMMON_DIR": str(self.base / "other"),
        }):
            self.assertEqual(
                self.message(), "Copilot needs your attention: répo with spaces [feature/slash]"
            )

    def test_git_calls_share_one_fifteen_second_budget(self):
        result = subprocess.CompletedProcess(["git"], 0, str(self.repo) + "\n", "")
        with mock.patch.object(context.time, "monotonic", autospec=True, side_effect=[0, 1, 16]), \
             mock.patch.object(context.subprocess, "run", autospec=True, return_value=result) as run:
            with self.assertRaises(context.ContextError) as raised:
                context.resolve_context(self.event())
        self.assertEqual(raised.exception.code, "git_timeout")
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.kwargs["timeout"], 14)

    def test_unexpected_filesystem_error_is_explicit(self):
        with mock.patch.object(context.os, "stat", autospec=True, side_effect=OSError("private")):
            with self.assertRaises(context.ContextError) as raised:
                context.resolve_context(self.event())
        self.assertEqual(raised.exception.code, "cwd_unavailable")

    def test_invalid_cwd_has_a_structured_error(self):
        with self.assertRaises(context.ContextError) as raised:
            context.resolve_context(self.event("/invalid\x00cwd"))
        self.assertEqual(raised.exception.code, "cwd_unavailable")

    def test_git_execution_errors_and_timeouts_are_explicit(self):
        failures = [
            (FileNotFoundError("secret"), "git_execution_failed"),
            (PermissionError("secret"), "git_execution_failed"),
            (subprocess.TimeoutExpired(["git"], 15), "git_timeout"),
        ]
        for failure, code in failures:
            with self.subTest(code=code), mock.patch.object(
                context.subprocess, "run", autospec=True, side_effect=failure
            ) as run:
                with self.assertRaises(context.ContextError) as raised:
                    context.resolve_context(self.event())
                self.assertEqual(raised.exception.code, code)
                self.assertNotIn("secret", str(raised.exception))
                self.assertLessEqual(run.call_args.kwargs["timeout"], 15)

    def test_unexpected_git_exit_is_not_non_git_absence(self):
        for code, error in ((128, "fatal: corrupt repository"), (1, "unexpected failure")):
            result = subprocess.CompletedProcess(["git"], code, "", error)
            with self.subTest(code=code), mock.patch.object(
                context.subprocess, "run", autospec=True, return_value=result
            ):
                with self.assertRaises(context.ContextError) as raised:
                    context.resolve_context(self.event())
                self.assertEqual(raised.exception.code, "git_failed")


if __name__ == "__main__":
    unittest.main()
