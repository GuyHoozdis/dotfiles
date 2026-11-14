import contextlib
import io
import json
import os
import select
import socket
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "share" / "copilot"
sys.path.insert(0, str(PACKAGE))

from iterm_notifications import cli, spool
from iterm_notifications.context import HookEvent
from iterm_notifications.diagnostics import DiagnosticError
from iterm_notifications.worker import DeliveryError


ENTRY = ROOT / "bin" / "copilot-iterm-notify.py"
STATUS = ROOT / "bin" / "copilot-iterm-status"
SESSION_ID = "12345678-1234-1234-1234-123456789abc"
ITERM_ID = "w0t1p2:" + SESSION_ID.upper()
DRIVER = (
    "import os, sys\n"
    "from pathlib import Path\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "from iterm_notifications import cli\n"
    "launcher = cli.WorkerLauncher(sys.argv[3], Path(sys.argv[4]))\n"
    "raise SystemExit(cli.run_hook(sys.argv[2], sys.stdin.buffer, os.environ, launcher))\n"
)
FAKE_WORKER = (
    "import json, os, socket, sys\n"
    "client = socket.socket(socket.AF_UNIX)\n"
    "client.connect(os.environ['FAKE_WORKER_SOCKET'])\n"
    "null = os.stat(os.devnull).st_rdev\n"
    "report = {'argv': sys.argv[1:], 'pid': os.getpid(), 'sid': os.getsid(0),\n"
    "          'devnull': [os.fstat(fd).st_rdev == null for fd in (0, 1, 2)],\n"
    "          'executable': sys.executable}\n"
    "client.sendall(json.dumps(report).encode() + b'\\n')\n"
    "client.recv(1)\n"
)


class HookTestCase(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.env = {"PATH": os.environ["PATH"], "HOME": directory.name, "TMPDIR": directory.name}

    def session_dir(self):
        return self.root / "copilot-iterm-status" / SESSION_ID.upper()

    def queue_names(self):
        return sorted(os.listdir(self.session_dir() / "notification-queue"))

    def run_entry(self, *args, data=b"{}", env=None):
        return subprocess.run(
            [sys.executable, str(ENTRY), *args], input=data, capture_output=True,
            env=self.env if env is None else env, timeout=30, check=False,
        )

    def run_driver(self, event, python, entry, data=b"{}", extra=None):
        env = self.env | {"ITERM_SESSION_ID": ITERM_ID} | (extra or {})
        return subprocess.run(
            [sys.executable, "-c", DRIVER, str(PACKAGE), event, python, str(entry)],
            input=data, capture_output=True, env=env, timeout=30, check=False,
        )

    def codes(self, stderr):
        return [json.loads(line)["code"] for line in stderr.decode().splitlines()]


class EntrypointTests(HookTestCase):
    def test_entrypoint_is_executable_uv_script(self):
        self.assertTrue(os.access(ENTRY, os.X_OK))
        text = ENTRY.read_text()
        self.assertTrue(text.startswith("#!/usr/bin/env -S uv run --script\n"))
        self.assertIn('requires-python = ">=3.12"', text)
        self.assertIn('dependencies = ["iterm2"]', text)
        self.assertTrue(ENTRY.with_name(ENTRY.name + ".lock").is_file())

    def test_help_has_no_effects(self):
        result = self.run_entry("--help", env=self.env | {"ITERM_SESSION_ID": ITERM_ID})
        self.assertEqual(result.returncode, 0)
        self.assertIn(b"usage:", result.stdout)
        self.assertNotIn(b"--worker", result.stdout)
        self.assertEqual(os.listdir(self.root), [])

    def test_cli_misuse_is_nonzero(self):
        for args in ((), ("Stop", "--worker", SESSION_ID), ("--worker", "../bad")):
            with self.subTest(args=args):
                result = self.run_entry(*args)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")
        self.assertEqual(os.listdir(self.root), [])

    def test_missing_iterm_session_or_tmux_is_silent_noop(self):
        for extra in ({}, {"ITERM_SESSION_ID": ""}, {"ITERM_SESSION_ID": ITERM_ID, "TMUX": "x"}):
            with self.subTest(extra=extra):
                result = self.run_entry("Notification", data=b"not json", env=self.env | extra)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"", b""))
        self.assertEqual(os.listdir(self.root), [])

    def test_handled_input_and_filesystem_failures_exit_zero_with_sanitized_stderr(self):
        secret = b"private prompt rm -rf"
        file_root = self.root / "file"
        file_root.write_text("")
        cases = [
            ("Notification", b'{"prompt": "' + secret + b'"', ITERM_ID, {}, "invalid_json"),
            ("Notification", b" " * (10 * 1024 * 1024 + 1), ITERM_ID, {}, "input_too_large"),
            ("Notification", b"[]", ITERM_ID, {}, "invalid_payload"),
            ("Notification", b"{}", "w0:not-a-uuid " + secret.decode(), {}, "invalid_source_uuid"),
            ("Bogus", b"{}", ITERM_ID, {}, "invalid_event"),
            ("Stop", b'{"cwd": "' + secret + b'"}', ITERM_ID, {"TMPDIR": str(file_root)},
             "spool_unavailable"),
        ]
        for event, data, session, extra, code in cases:
            with self.subTest(code=code):
                env = self.env | {"ITERM_SESSION_ID": session} | extra
                result = self.run_entry(event, data=data, env=env)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")
                self.assertEqual(self.codes(result.stderr), [code])
                self.assertNotIn(b"private", result.stderr)
        self.assertFalse((self.root / "copilot-iterm-status").exists())

    def test_symlinked_session_directory_is_handled_failure(self):
        (self.root / "copilot-iterm-status").mkdir()
        (self.root / "copilot-iterm-status" / SESSION_ID.upper()).symlink_to(self.root)
        result = self.run_entry("Stop", env=self.env | {"ITERM_SESSION_ID": ITERM_ID})
        self.assertEqual((result.returncode, result.stdout), (0, b""))
        self.assertEqual(self.codes(result.stderr), ["spool_unsafe"])


class LaunchTests(HookTestCase):
    def test_default_launcher_uses_resolved_entry_and_interpreter(self):
        self.assertEqual(cli.DEFAULT_LAUNCHER, cli.WorkerLauncher(sys.executable, ENTRY))
        self.assertTrue(cli.DEFAULT_LAUNCHER.entry.is_absolute())

    def test_worker_launch_failure_keeps_record_queued(self):
        result = self.run_driver("Stop", str(self.root / "missing-python"), ENTRY)
        self.assertEqual((result.returncode, result.stdout), (0, b""))
        self.assertEqual(self.codes(result.stderr), ["worker_launch_failed"])
        self.assertEqual(self.queue_names(), ["00000000000000000001.event"])

    def test_detached_worker_survives_producer_and_releases_hook_pipes(self):
        fake = self.root / "fake-worker.py"
        fake.write_text(FAKE_WORKER)
        address = str(self.root / "w.sock")
        server = socket.socket(socket.AF_UNIX)
        self.addCleanup(server.close)
        server.bind(address)
        server.listen(1)
        server.settimeout(30)
        result = self.run_driver(
            "Notification", sys.executable, fake,
            data=b'{"notification_type": "permission_prompt", "prompt": "private"}',
            extra={"FAKE_WORKER_SOCKET": address},
        )
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"", b""))
        connection, _ = server.accept()
        self.addCleanup(connection.close)
        connection.settimeout(30)
        report = json.loads(connection.makefile("rb").readline())
        self.assertEqual(report["argv"], ["--worker", SESSION_ID])
        self.assertEqual(report["executable"], sys.executable)
        self.assertEqual(report["sid"], report["pid"])
        self.assertEqual(report["devnull"], [True, True, True])
        os.kill(report["pid"], 0)
        self.assertEqual(self.queue_names(), ["00000000000000000001.event"])
        record = (self.session_dir() / "notification-queue" / self.queue_names()[0]).read_text()
        self.assertNotIn("private", record)
        connection.sendall(b"x")
        self.assertEqual(connection.recv(1), b"")


class WorkerProcessTests(HookTestCase):
    def enqueue(self, name, kind=None):
        with spool.Spool.open(SESSION_ID, self.env) as opened:
            opened.enqueue(HookEvent(name, "/source", kind, SESSION_ID))

    def worker(self, **kwargs):
        return subprocess.Popen(
            [sys.executable, str(ENTRY), "--worker", SESSION_ID], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.env, **kwargs,
        )

    def test_terminal_api_unavailable_is_logged_without_stdout(self):
        self.enqueue("Notification", "permission_prompt")
        process = self.worker()
        stdout, stderr = process.communicate(timeout=30)
        self.assertEqual((process.returncode, stdout), (0, b""))
        self.assertEqual(self.codes(stderr), ["terminal_api_unavailable"])
        log = (self.session_dir() / "notification-errors.log").read_bytes()
        self.assertEqual(self.codes(log), ["terminal_api_unavailable"])
        self.assertEqual(self.queue_names(), [])

    def test_injected_delivery_failure_is_logged_without_raw_error_or_stdout(self):
        self.enqueue("Notification", "permission_prompt")
        stdout, stderr = io.StringIO(), io.StringIO()

        def fail(_action, _event):
            raise DeliveryError("tty_write_failed") from OSError("private tty path")

        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = cli.run_worker(
                SESSION_ID, self.env, lambda: contextlib.nullcontext(fail),
            )

        self.assertEqual((result, stdout.getvalue()), (0, ""))
        self.assertEqual(self.codes(stderr.getvalue().encode()), ["tty_write_failed"])
        self.assertNotIn("private tty path", stderr.getvalue())
        self.assertEqual(self.queue_names(), [])

    def test_default_sink_focus_diagnostic_is_logged_under_worker_lock(self):
        self.enqueue("Notification", "permission_prompt")
        stdout, stderr = io.StringIO(), io.StringIO()

        def fake_open_sink(*, report):
            def sink(_action, _event):
                report(DiagnosticError("focus_unknown"))

            return contextlib.nullcontext(sink)

        with patch("iterm_notifications.terminal.open_sink", side_effect=fake_open_sink):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                result = cli.run_worker(SESSION_ID, self.env)

        self.assertEqual((result, stdout.getvalue()), (0, ""))
        self.assertEqual(self.codes(stderr.getvalue().encode()), ["focus_unknown"])
        log = (self.session_dir() / "notification-errors.log").read_bytes()
        self.assertEqual(self.codes(log), ["focus_unknown"])
        self.assertEqual(self.queue_names(), [])

    def test_killed_owner_releases_lock_and_aged_metadata_never_steals_live_lock(self):
        holder_code = (
            "import os, sys\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "from iterm_notifications import spool\n"
            "opened = spool.Spool.open(sys.argv[2], os.environ)\n"
            "with opened.worker_lock():\n"
            "    print('locked', flush=True)\n"
            "    sys.stdin.read()\n"
        )
        holder = subprocess.Popen(
            [sys.executable, "-c", holder_code, str(PACKAGE), SESSION_ID],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=self.env,
        )
        self.addCleanup(holder.stdin.close)
        self.addCleanup(holder.stdout.close)
        self.assertEqual(holder.stdout.readline(), b"locked\n")
        lock = self.session_dir() / "notification.lock"
        self.assertEqual(lock.read_text(), f"{holder.pid}\n")
        os.utime(lock, (0, 0))
        inode = lock.stat().st_ino
        self.enqueue("Stop")
        contender = self.worker()
        with self.assertRaises(subprocess.TimeoutExpired):
            contender.wait(timeout=0.5)
        self.assertEqual(self.queue_names(), ["00000000000000000001.event"])
        holder.kill()
        holder.wait(timeout=30)
        stdout, stderr = contender.communicate(timeout=30)
        self.assertEqual((contender.returncode, stdout), (0, b""))
        self.assertEqual(self.codes(stderr), ["terminal_api_unavailable"])
        self.assertEqual(self.queue_names(), [])
        self.assertEqual(lock.stat().st_ino, inode)


class StatusCoexistenceTests(HookTestCase):
    def test_status_session_end_preserves_attention_queue_and_lock(self):
        fake_it2 = self.root / "it2"
        fake_it2.write_text("#!/bin/sh\nexit 0\n")
        fake_it2.chmod(stat.S_IRWXU)
        with spool.Spool.open(SESSION_ID, self.env) as opened:
            opened.enqueue(HookEvent("Notification", "/source", "permission_prompt", SESSION_ID))
            lock = self.session_dir() / "notification.lock"
            with opened.worker_lock():
                inode = lock.stat().st_ino
                read_end, write_end = os.pipe()
                self.addCleanup(os.close, read_end)
                process = subprocess.Popen(
                    [str(STATUS), "SessionEnd"], stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, pass_fds=(write_end,),
                    env=self.env | {"ITERM_SESSION_ID": ITERM_ID, "IT2": str(fake_it2)},
                )
                os.close(write_end)
                self.assertEqual(process.wait(timeout=30), 0)
                while True:
                    ready, _, _ = select.select([read_end], [], [], 30)
                    self.assertEqual(ready, [read_end])
                    if not os.read(read_end, 4096):
                        break
                self.assertEqual(lock.stat().st_ino, inode)
                self.assertEqual(self.queue_names(), ["00000000000000000001.event"])
                self.assertFalse((self.session_dir() / "lock").exists())
                self.assertTrue((self.session_dir() / "latest").read_text().endswith(" cleared\n"))


if __name__ == "__main__":
    unittest.main()
