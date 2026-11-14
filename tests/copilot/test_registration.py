import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / "share/copilot/hooks/iterm2-session-status.json"
PROFILE = ROOT / "etc/iterm/DynamicProfiles/copilot-agents.json"
EVENTS = (
    "SessionStart",
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    "Notification",
    "Stop",
    "SessionEnd",
)
RECORDER = (
    f"#!{sys.executable}\n"
    "import json, os, sys\n"
    "from pathlib import Path\n"
    "name = Path(sys.argv[0]).name\n"
    "record = {'argv': sys.argv[1:], 'stdin': sys.stdin.buffer.read().hex()}\n"
    "(Path(os.environ['HOME']) / (name + '.json')).write_text(json.dumps(record))\n"
    "if name.endswith('.py'):\n"
    "    raise SystemExit(int(os.environ.get('ATTENTION_EXIT', '0')))\n"
)


class HookRegistrationTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory(prefix=".registration-", dir=ROOT)
        self.addCleanup(directory.cleanup)
        self.home = Path(directory.name) / "home with spaces"
        bin_dir = self.home / "dotfiles/bin"
        bin_dir.mkdir(parents=True)
        for name in ("copilot-iterm-status", "copilot-iterm-notify.py"):
            executable = bin_dir / name
            executable.write_text(RECORDER)
            executable.chmod(0o700)
        self.env = {"PATH": os.environ["PATH"], "HOME": str(self.home)}
        self.registration = json.loads(HOOKS.read_text())
        self.hooks = self.registration["hooks"]

    def run_command(
        self,
        command: str,
        payload: bytes,
        *,
        extra: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            ["/bin/bash", "-c", command],
            input=payload,
            capture_output=True,
            env=self.env | (extra or {}),
            timeout=10,
            check=False,
        )

    def recorded(self, name: str) -> dict[str, object]:
        return json.loads((self.home / (name + ".json")).read_text())

    def test_each_registered_command_receives_original_event_and_stdin(self) -> None:
        self.assertEqual(self.registration["version"], 1)
        self.assertEqual(set(self.hooks), set(EVENTS))
        for event in EVENTS:
            with self.subTest(event=event):
                entries = self.hooks[event]
                self.assertEqual(len(entries), 2)
                expected_status = {
                    "type": "command",
                    "bash": f'"$HOME/dotfiles/bin/copilot-iterm-status" {event}',
                    "timeoutSec": 5,
                }
                if event == "Notification":
                    expected_status["matcher"] = "permission_prompt|elicitation_dialog"
                self.assertEqual(entries[0], expected_status)
                self.assertEqual(
                    entries[1],
                    expected_status
                    | {
                        "bash": f'"$HOME/dotfiles/bin/copilot-iterm-notify.py" {event}',
                    },
                )
                payload = (
                    json.dumps(
                        {
                            "event": event,
                            "cwd": "/repo with spaces",
                            "notification_type": "permission_prompt",
                        }
                    ).encode()
                    + b"\n"
                )
                for entry in entries:
                    result = self.run_command(entry["bash"], payload)
                    self.assertEqual(
                        (result.returncode, result.stdout, result.stderr),
                        (0, b"", b""),
                    )
                expected = {"argv": [event], "stdin": payload.hex()}
                self.assertEqual(self.recorded("copilot-iterm-status"), expected)
                self.assertEqual(self.recorded("copilot-iterm-notify.py"), expected)

    def test_only_attention_notifications_reach_both_commands(self) -> None:
        for event, entries in self.hooks.items():
            with self.subTest(event=event):
                self.assertEqual(len(entries), 2)
                for entry in entries:
                    if event != "Notification":
                        self.assertNotIn("matcher", entry)
                        continue
                    for kind in ("permission_prompt", "elicitation_dialog", "other", ""):
                        matched = re.fullmatch(entry["matcher"], kind) is not None
                        self.assertEqual(
                            matched,
                            kind in ("permission_prompt", "elicitation_dialog"),
                        )

    def test_attention_launch_or_worker_failure_does_not_consume_status_input(self) -> None:
        attention = self.home / "dotfiles/bin/copilot-iterm-notify.py"
        for failure in ("worker", "launch"):
            with self.subTest(failure=failure):
                if failure == "launch":
                    attention.unlink()
                for event in EVENTS:
                    with self.subTest(event=event):
                        entries = self.hooks[event]
                        self.assertEqual(len(entries), 2)
                        payload = json.dumps({"event": event}).encode() + b"\n"
                        failed = self.run_command(
                            entries[1]["bash"],
                            payload,
                            extra={"ATTENTION_EXIT": "1"},
                        )
                        self.assertNotEqual(failed.returncode, 0)
                        self.assertEqual(failed.stdout, b"")
                        if failure == "worker":
                            self.assertEqual(
                                self.recorded("copilot-iterm-notify.py"),
                                {"argv": [event], "stdin": payload.hex()},
                            )
                        result = self.run_command(entries[0]["bash"], payload)
                        self.assertEqual(
                            (result.returncode, result.stdout, result.stderr),
                            (0, b"", b""),
                        )
                        self.assertEqual(
                            self.recorded("copilot-iterm-status"),
                            {"argv": [event], "stdin": payload.hex()},
                        )


class ProfileAlertPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        profiles = json.loads(PROFILE.read_text())["Profiles"]
        self.assertEqual(len(profiles), 1)
        self.profile = profiles[0]
        # Inherited settings must not turn a completion bell into a popup,
        # silence it, or suppress adapter-approved background-window alerts.
        self.inherited = {
            "BM Growl": False,
            "Send Terminal Generated Alerts": False,
            "Send Bell Alert": True,
            "Send Idle Alert": True,
            "Send New Output Alert": True,
            "Send Session Ended Alert": True,
            "Suppress Alerts in Active Session": True,
            "Send Alerts To Companion": True,
            "Silence Bell": True,
        }
        self.effective = self.inherited | self.profile

    def test_only_osc9_produces_native_alerts_even_in_active_background_session(self) -> None:
        settings = self.effective
        sources = {
            "osc9": "Send Terminal Generated Alerts",
            "bel": "Send Bell Alert",
            "idle": "Send Idle Alert",
            "output": "Send New Output Alert",
            "session_end": "Send Session Ended Alert",
        }
        for source, setting in sources.items():
            for active in (False, True):
                for companion in (False, True):
                    with self.subTest(source=source, active=active, companion=companion):
                        permitted = (
                            settings["BM Growl"]
                            and settings[setting]
                            and not (active and settings["Suppress Alerts in Active Session"])
                            and (not companion or settings["Send Alerts To Companion"])
                        )
                        self.assertEqual(permitted, source == "osc9" and not companion)

    def test_completion_remains_audible_without_changing_profile_identity(self) -> None:
        self.assertIs(self.effective["Silence Bell"], False)
        self.assertEqual(
            {key: value for key, value in self.profile.items() if key not in self.inherited},
            {
                "Name": "Copilot Agents",
                "Guid": "870214EA-844A-4654-A241-B7EB0B766076",
                "Dynamic Profile Parent Name": "Default",
                "Tags": ["copilot"],
                "Title Components": 32,
                "Use Custom Tab Title": True,
                "Custom Tab Title": "\\(currentSession.user.repoLabel)",
            },
        )


if __name__ == "__main__":
    unittest.main()
