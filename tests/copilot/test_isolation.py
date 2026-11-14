import os
import select
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

from iterm_notifications import ipc, isolation
from iterm_notifications.context import HookEvent
from iterm_notifications.worker import DeliveryError


SOURCE_ID = "12345678-1234-1234-1234-123456789abc"
DEEP_JSON = b"[" * 100000
CORRUPT_REPLIES = {
    "array": b"[]",
    "kind_object": b'{"v": 1, "type": {}}',
    "kind_array": b'{"v": 1, "type": []}',
    "deep": DEEP_JSON[:8000],
    "invalid_utf8": b"\xff\xfe",
}
# Holds an inherited probe write end open until killed; the test sees EOF on death.
GRANDCHILD = "import threading; threading.Event().wait()"
FAKE_HELPER = r'''
import json, os, subprocess, sys, threading
mode, probe = sys.argv[1], int(sys.argv[2])
corrupt = {name: bytes.fromhex(value) for name, value in json.loads(sys.argv[3]).items()}
def send(**message):
    os.write(1, (json.dumps({"v": 1, **message}) + "\n").encode())
def hang():
    threading.Event().wait()
if mode == "auth_grandchild":
    subprocess.Popen(
        [sys.executable, "-c", sys.argv[4]], stdin=subprocess.DEVNULL, pass_fds=(probe,),
    )
os.close(probe)
if mode == "auth_grandchild":
    hang()
send(type="ready")
while line := sys.stdin.buffer.readline():
    request = json.loads(line)
    if mode == "block":
        hang()
    if mode == "partial":
        os.write(1, b'{"v": 1')
        sys.exit(0)
    if mode == "overflow":
        os.write(1, b"x" * 70000)
        hang()
    if mode in corrupt:
        os.write(1, corrupt[mode] + b"\n")
        hang()
    if request["event"]["cwd"] == "/die":
        sys.exit(0)
    send(type="diagnostic", code="focus_unknown", error="RPCException")
    send(type="done")
if mode == "close_hang":
    hang()
'''
WATCHDOG_HELPER = r'''
import os, subprocess, sys, threading
sys.path.insert(0, sys.argv[1])
from iterm_notifications import helper
probe = int(sys.argv[2])
helper.watch_lifeline(int(sys.argv[3]))
subprocess.Popen(
    [sys.executable, "-c", sys.argv[4]], stdin=subprocess.DEVNULL, pass_fds=(probe,),
)
os.close(probe)
os.write(1, b"ready\n")
threading.Event().wait()
'''


def kill_unreaped_group(process):
    """Bounded cleanup for a still-unreaped helper so failures never leak its group."""
    if process.returncode is None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        process.wait(timeout=5)


def read_before(fd, timeout=5.0):
    """Read once, failing instead of hanging if nothing arrives by the deadline."""
    ready, _, _ = select.select([fd], [], [], timeout)
    if not ready:
        raise AssertionError("no data or EOF before deadline")
    return os.read(fd, 64)


class IsolatedSinkTests(unittest.TestCase):
    def setUp(self):
        self.diagnostics = []
        self.processes = []
        self.probe_read, self.probe_write = os.pipe()
        self.addCleanup(os.close, self.probe_read)
        real_popen = subprocess.Popen

        def spawn(*args, **kwargs):
            kwargs["pass_fds"] = (*kwargs.get("pass_fds", ()), self.probe_write)
            process = real_popen(*args, **kwargs)
            self.addCleanup(kill_unreaped_group, process)
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
        corrupt = "{" + ",".join(
            f'"{name}": "{value.hex()}"' for name, value in CORRUPT_REPLIES.items()
        ) + "}"
        command = [
            sys.executable, "-c", FAKE_HELPER, mode, str(self.probe_write), corrupt, GRANDCHILD,
        ]
        return isolation.open_sink(report=self.diagnostics.append, command=command)

    def event(self, cwd="/source"):
        return HookEvent("Notification", cwd, "permission_prompt", SOURCE_ID)

    def codes(self):
        return [diagnostic.code for diagnostic in self.diagnostics]

    def assert_probe_closed(self):
        os.close(self.probe_write)
        self.assertEqual(read_before(self.probe_read), b"")

    def assert_failure(self, mode, code):
        with self.open(mode) as sink:
            with self.assertRaises(DeliveryError) as raised:
                sink("waiting", self.event())
        self.assertEqual(raised.exception.code, code)
        self.assertIsNotNone(self.processes[0].returncode)
        self.assert_probe_closed()

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
        self.assert_probe_closed()

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

    def test_corrupt_replies_are_protocol_errors_and_kill_helper(self):
        for mode in CORRUPT_REPLIES:
            with self.subTest(mode=mode):
                self.processes.clear()
                with self.open(mode) as sink:
                    with self.assertRaises(DeliveryError) as raised:
                        sink("waiting", self.event())
                self.assertEqual(raised.exception.code, "terminal_helper_protocol")
                self.assertEqual(self.processes[0].returncode, -signal.SIGKILL)

    def test_helper_exit_fails_action_and_later_action_uses_replacement(self):
        with self.open("echo") as sink:
            with self.assertRaises(DeliveryError) as raised:
                sink("waiting", self.event("/die"))
            sink("done", self.event())

        self.assertEqual(raised.exception.code, "terminal_helper_exited")
        self.assertEqual(len(self.processes), 2)
        self.assertEqual(self.codes(), ["focus_unknown"])


class ProtocolDecodeTests(unittest.TestCase):
    def test_malformed_messages_are_protocol_errors(self):
        for line in (*CORRUPT_REPLIES.values(), DEEP_JSON, b'{"v": 1, "type": "failed", "code": []}'):
            with self.subTest(line=line[:24]):
                with self.assertRaises(DeliveryError) as raised:
                    ipc.decode_message(line)
                self.assertEqual(raised.exception.code, "terminal_helper_protocol")

    def test_malformed_requests_are_protocol_errors(self):
        event = '{"event": "Stop", "cwd": null, "notification_type": null, "source_uuid": "x"}'
        for line in (
            b"[]", DEEP_JSON, b'{"v": 1, "action": [], "event": ' + event.encode() + b"}",
            b'{"v": 1, "action": {}, "event": ' + event.encode() + b"}",
            b'{"v": 1, "action": "done", "event": []}',
        ):
            with self.subTest(line=line[:24]):
                with self.assertRaises(DeliveryError) as raised:
                    ipc.decode_request(line)
                self.assertEqual(raised.exception.code, "terminal_helper_protocol")


class LifelineTests(unittest.TestCase):
    def test_helper_group_dies_when_parent_lifeline_closes_during_hang(self):
        lifeline_read, lifeline_write = os.pipe()
        probe_read, probe_write = os.pipe()
        self.addCleanup(os.close, probe_read)
        process = subprocess.Popen(
            [
                sys.executable, "-c", WATCHDOG_HELPER, str(PACKAGE), str(probe_write),
                str(lifeline_read), GRANDCHILD,
            ],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            start_new_session=True, pass_fds=(lifeline_read, probe_write),
        )
        self.addCleanup(kill_unreaped_group, process)
        self.addCleanup(process.stdout.close)
        os.close(lifeline_read)
        os.close(probe_write)
        self.assertEqual(read_before(process.stdout.fileno()), b"ready\n")

        os.close(lifeline_write)

        self.assertEqual(process.wait(timeout=5), -signal.SIGKILL)
        self.assertEqual(read_before(probe_read), b"")


if __name__ == "__main__":
    unittest.main()
