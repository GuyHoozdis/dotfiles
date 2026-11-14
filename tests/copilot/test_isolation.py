import os
import signal
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "share" / "copilot"
sys.path.insert(0, str(PACKAGE))

from iterm_notifications import isolation
from iterm_notifications.context import HookEvent
from iterm_notifications.worker import DeliveryError


SOURCE_ID = "12345678-1234-1234-1234-123456789abc"
FAKE_HELPER = r'''
import json, os, subprocess, sys, time
mode = sys.argv[1]
def send(**message):
    os.write(1, (json.dumps({"v": 1, **message}) + "\n").encode())
if mode == "auth_grandchild":
    child = subprocess.Popen(["sleep", "60"])
    send(type="diagnostic", code=f"pid_{child.pid}", error="Exception")
    time.sleep(60)
send(type="ready")
while line := sys.stdin.buffer.readline():
    request = json.loads(line)
    if mode == "block":
        time.sleep(60)
    if mode == "partial":
        os.write(1, b'{"v": 1')
        sys.exit(0)
    if mode == "overflow":
        os.write(1, b"x" * 70000)
        time.sleep(60)
    if request["event"]["cwd"] == "/die":
        sys.exit(0)
    send(type="diagnostic", code="focus_unknown", error="RPCException")
    send(type="done")
if mode == "close_hang":
    time.sleep(60)
'''
WATCHDOG_HELPER = r'''
import json, os, subprocess, sys, time
sys.path.insert(0, sys.argv[1])
from iterm_notifications import helper
helper.watch_lifeline(int(sys.argv[2]))
child = subprocess.Popen(["sleep", "60"])
os.write(1, (json.dumps({"grandchild": child.pid}) + "\n").encode())
time.sleep(60)
'''


def wait_gone(pid, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    return False


class IsolatedSinkTests(unittest.TestCase):
    def setUp(self):
        self.diagnostics = []
        self.processes = []
        real_popen = subprocess.Popen

        def spawn(*args, **kwargs):
            process = real_popen(*args, **kwargs)
            self.processes.append(process)
            return process

        for name, value in (("ACTION_TIMEOUT", 1.0), ("CLOSE_GRACE", 0.5)):
            patcher = patch.object(isolation, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        popen = patch.object(isolation.subprocess, "Popen", side_effect=spawn)
        popen.start()
        self.addCleanup(popen.stop)

    def open(self, mode):
        return isolation.open_sink(
            report=self.diagnostics.append, command=[sys.executable, "-c", FAKE_HELPER, mode],
        )

    def event(self, cwd="/source"):
        return HookEvent("Notification", cwd, "permission_prompt", SOURCE_ID)

    def codes(self):
        return [diagnostic.code for diagnostic in self.diagnostics]

    def assert_failure(self, mode, code):
        with self.open(mode) as sink:
            with self.assertRaises(DeliveryError) as raised:
                sink("waiting", self.event())
        self.assertEqual(raised.exception.code, code)
        self.assertIsNotNone(self.processes[0].returncode)

    def test_action_reply_forwards_diagnostics_and_helper_is_reaped(self):
        with self.open("echo") as sink:
            sink("waiting", self.event())
            self.assertIsNone(self.processes[0].returncode)
            self.assertEqual(os.getpgid(self.processes[0].pid), self.processes[0].pid)

        self.assertEqual(self.codes(), ["focus_unknown"])
        self.assertIsNotNone(self.processes[0].returncode)

    def test_blocked_action_times_out_and_kills_owned_group(self):
        started = time.monotonic()

        self.assert_failure("block", "terminal_helper_timeout")

        self.assertLess(time.monotonic() - started, 4)
        self.assertEqual(self.processes[0].returncode, -signal.SIGKILL)

    def test_hung_authentication_grandchild_is_killed_with_helper(self):
        with self.open("auth_grandchild") as sink:
            with self.assertRaises(DeliveryError) as raised:
                sink("done", self.event())

        self.assertEqual(raised.exception.code, "terminal_helper_timeout")
        grandchild = int(self.codes()[0].removeprefix("pid_"))
        self.assertTrue(wait_gone(grandchild))

    def test_hung_close_is_killed_without_undoing_completed_action(self):
        started = time.monotonic()
        with self.open("close_hang") as sink:
            sink("done", self.event())

        self.assertLess(time.monotonic() - started, 4)
        self.assertEqual(self.codes(), ["focus_unknown", "terminal_helper_close_timeout"])
        self.assertEqual(self.processes[0].returncode, -signal.SIGKILL)

    def test_partial_reply_before_eof_is_rejected(self):
        self.assert_failure("partial", "terminal_helper_partial_reply")

    def test_oversized_reply_is_rejected(self):
        self.assert_failure("overflow", "terminal_helper_reply_too_large")

    def test_helper_exit_fails_action_and_later_action_uses_replacement(self):
        with self.open("echo") as sink:
            with self.assertRaises(DeliveryError) as raised:
                sink("waiting", self.event("/die"))
            sink("done", self.event())

        self.assertEqual(raised.exception.code, "terminal_helper_exited")
        self.assertEqual(len(self.processes), 2)
        self.assertEqual(self.codes(), ["focus_unknown"])


class LifelineTests(unittest.TestCase):
    def test_helper_group_dies_when_parent_lifeline_closes_during_hang(self):
        read_end, write_end = os.pipe()
        process = subprocess.Popen(
            [sys.executable, "-c", WATCHDOG_HELPER, str(PACKAGE), str(read_end)],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            start_new_session=True, pass_fds=(read_end,),
        )
        os.close(read_end)
        self.addCleanup(process.stdout.close)
        grandchild = int(process.stdout.readline().split(b":")[1].strip(b" }\n"))

        os.close(write_end)

        self.assertEqual(process.wait(timeout=5), -signal.SIGKILL)
        self.assertTrue(wait_gone(grandchild))


if __name__ == "__main__":
    unittest.main()
