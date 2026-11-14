import contextlib
import io
import os
import pty
import signal
import time
import stat
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "share" / "copilot"))

from iterm_notifications import terminal, terminal_api
from iterm_notifications.context import HookEvent
from iterm_notifications.diagnostics import diagnostic_line
from iterm_notifications.worker import DeliveryError


SOURCE_ID = "12345678-1234-1234-1234-123456789abc"
OTHER_ID = "87654321-4321-4321-4321-cba987654321"
PROFILE_ID = "870214EA-844A-4654-A241-B7EB0B766076"


class FakeProfile:
    def __init__(self, original_guid=PROFILE_ID, guid="locally-edited", name="renamed"):
        self.original_guid = original_guid
        self.guid = guid
        self.name = name


class FakeSession:
    def __init__(self, session_id, *, profile=None, tty="/dev/ttys001", repo_label="repo|worktree"):
        self.session_id = session_id
        self.profile = profile
        self.variables = {"tty": tty, "user.repoLabel": repo_label}
        self.keyboard_calls = 0

    async def async_get_profile(self):
        return self.profile

    async def async_get_variable(self, name):
        return self.variables.get(name)

    def send_text(self, _text):
        self.keyboard_calls += 1
        raise AssertionError("keyboard input is never an alert transport")


class FakeTab:
    def __init__(self, tab_id, current_session):
        self.tab_id = tab_id
        self.current_session = current_session


class FakeWindow:
    def __init__(self, window_id, current_tab):
        self.window_id = window_id
        self.current_tab = current_tab


class FakeApp:
    def __init__(self, sessions, source, *, active=False, focus_error=None):
        self.sessions = {session.session_id: session for session in sessions}
        self.source = source
        self.app_active = active
        self.window = FakeWindow("window-source", FakeTab("tab-source", source))
        self.current_window = self.window
        self.focus_error = focus_error
        self.lookups = []
        self.refreshes = 0

    def get_session_by_id(self, session_id, include_buried=True):
        self.lookups.append(session_id)
        return self.sessions.get(session_id)

    async def async_refresh(self):
        self.refreshes += 1

    def get_window_and_tab_for_session(self, session):
        if self.focus_error:
            raise self.focus_error
        return self.window, self.window.current_tab


class FakeConnection:
    def __init__(self, app):
        self.app = app
        self.closed = False
        self.websocket = self

    async def close(self):
        self.closed = True


class FakeIterm(types.ModuleType):
    class RPCException(Exception):
        pass

    def __init__(self, app):
        super().__init__("iterm2")
        self.app = app
        self.connection = FakeConnection(app)
        self.connect_calls = 0

    class Connection:
        async def async_create(self):
            raise AssertionError("fake connection factory must be bound")

    async def async_get_app(self, connection):
        return connection.app

    def bind_connection(self):
        owner = self

        class Connection:
            @staticmethod
            async def async_create():
                owner.connect_calls += 1
                return owner.connection

        self.Connection = Connection


class FakeWebSocketException(Exception):
    pass


class FakeConnectionClosed(FakeWebSocketException):
    pass


class FakeSubscriptionException(Exception):
    pass


class TerminalAdapterTests(unittest.TestCase):
    def setUp(self):
        self.profile = FakeProfile()
        self.source = FakeSession(SOURCE_ID.upper(), profile=self.profile)
        self.app = FakeApp([self.source], self.source)
        self.iterm = FakeIterm(self.app)
        self.iterm.bind_connection()
        self.output = []
        self.diagnostics = []
        rpc = types.ModuleType("iterm2.rpc")
        rpc.RPCException = self.iterm.RPCException
        websockets = types.ModuleType("websockets")
        exceptions = types.ModuleType("websockets.exceptions")
        exceptions.WebSocketException = FakeWebSocketException
        notifications = types.ModuleType("iterm2.notifications")
        notifications.SubscriptionException = FakeSubscriptionException
        self.module_patch = patch.dict(sys.modules, {
            "iterm2": self.iterm, "iterm2.rpc": rpc, "iterm2.notifications": notifications,
            "websockets": websockets, "websockets.exceptions": exceptions,
        })
        self.module_patch.start()
        self.addCleanup(self.module_patch.stop)
        self.writer_patch = patch.object(
            terminal, "write_tty",
            side_effect=lambda tty, data: self.output.append((tty, data)),
        )
        self.writer_patch.start()
        self.addCleanup(self.writer_patch.stop)

    def deliver(self, action="waiting", event=None):
        if event is None:
            event = HookEvent("Notification", "/source/repo", "permission_prompt", SOURCE_ID)
        with terminal.open_sink(report=self.diagnostics.append) as sink:
            sink(action, event)

    def test_lowercase_event_uuid_finds_uppercase_live_session(self):
        self.deliver()

        self.assertEqual(self.app.lookups[0], SOURCE_ID.upper())
        self.assertEqual(len(self.output), 1)

    def test_legacy_unscoped_repo_label_is_not_used(self):
        self.source.variables = {"tty": "/dev/ttys001", "repoLabel": "legacy"}

        self.deliver()

        self.assertEqual(self.output[0][1], b"\x1b]9;Copilot needs your attention: repo\x07")

    def test_websocket_failure_during_connect_is_sanitized(self):
        async def fail_create():
            raise FakeConnectionClosed("private socket payload")

        self.iterm.Connection.async_create = staticmethod(fail_create)

        with self.assertRaises(DeliveryError) as raised:
            self.deliver()

        self.assertEqual(raised.exception.code, "iterm_connection_failed")
        self.assertNotIn("private", diagnostic_line(raised.exception.code, raised.exception))

    def test_websocket_failure_during_focus_logs_then_delivers(self):
        async def fail_refresh():
            raise FakeConnectionClosed("private focus payload")

        self.app.app_active = True
        self.app.async_refresh = fail_refresh

        self.deliver()

        self.assertEqual(self.diagnostics[0].code, "focus_unknown")
        self.assertEqual(len(self.output), 1)

    def test_subscription_failure_during_focus_logs_then_delivers(self):
        async def fail_refresh():
            raise FakeSubscriptionException("private subscription payload")

        self.app.app_active = True
        self.app.async_refresh = fail_refresh

        self.deliver()

        self.assertEqual(self.diagnostics[0].code, "focus_unknown")
        self.assertEqual(len(self.output), 1)

    def test_websocket_failure_reading_label_falls_back_to_source_context(self):
        original = self.source.async_get_variable

        async def fail_label(name):
            if name == "user.repoLabel":
                raise FakeConnectionClosed("private variable payload")
            return await original(name)

        self.source.async_get_variable = fail_label

        self.deliver()

        self.assertEqual(self.diagnostics[0].code, "source_context_unavailable")
        self.assertEqual(self.output[0][1], b"\x1b]9;Copilot needs your attention: repo\x07")

    def test_blocking_connection_setup_is_hard_bounded_and_restores_alarm(self):
        def previous_handler(_signum, _frame):
            raise AssertionError("previous alarm handler must not fire")

        async def blocking_create():
            signal.pause()
            raise AssertionError("blocking authentication should be interrupted")

        self.iterm.Connection.async_create = staticmethod(blocking_create)
        original = signal.signal(signal.SIGALRM, previous_handler)
        self.addCleanup(signal.signal, signal.SIGALRM, original)
        started = time.monotonic()

        with patch.object(terminal_api, "OPERATION_TIMEOUT", 0.05):
            with self.assertRaises(DeliveryError) as raised:
                self.deliver()

        self.assertLess(time.monotonic() - started, 2)
        self.assertEqual(raised.exception.code, "iterm_connection_failed")
        self.assertIs(signal.getsignal(signal.SIGALRM), previous_handler)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL), (0.0, 0.0))

    def test_library_output_is_silenced_while_diagnostics_still_report(self):
        async def noisy_refresh():
            print("private library stdout")
            print("private library stderr", file=sys.stderr)
            raise FakeConnectionClosed("private focus payload")

        self.app.app_active = True
        self.app.async_refresh = noisy_refresh
        stdout, stderr = io.StringIO(), io.StringIO()

        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            self.deliver()

        self.assertEqual((stdout.getvalue(), stderr.getvalue()), ("", ""))
        self.assertEqual(self.diagnostics[0].code, "focus_unknown")

    def test_library_exit_during_connect_is_delivery_failure(self):
        async def exit_create():
            raise SystemExit(1)

        self.iterm.Connection.async_create = staticmethod(exit_create)

        with self.assertRaises(DeliveryError) as raised:
            self.deliver()

        self.assertEqual(raised.exception.code, "iterm_api_incompatible")

    def test_explicit_source_lookup_never_falls_back_to_active_session(self):
        active = FakeSession(OTHER_ID.upper(), profile=self.profile)
        self.app.sessions = {active.session_id: active}
        self.app.active_session = active

        self.deliver()

        self.assertEqual(self.app.lookups, [SOURCE_ID.upper(), SOURCE_ID])
        self.assertEqual(self.output, [])
        self.assertEqual(active.keyboard_calls, 0)

    def test_matching_original_guid_allows_renamed_and_modified_profile(self):
        self.source.profile = FakeProfile(original_guid=PROFILE_ID, guid="edited", name="Renamed")

        self.deliver()

        self.assertEqual(len(self.output), 1)

    def test_guid_is_used_when_profile_has_no_original_guid(self):
        self.source.profile = types.SimpleNamespace(guid=PROFILE_ID, name="renamed")

        self.deliver()

        self.assertEqual(len(self.output), 1)

    def test_original_guid_precedes_a_matching_mutable_guid(self):
        self.source.profile = FakeProfile(original_guid="other-profile", guid=PROFILE_ID)

        self.deliver()

        self.assertEqual(self.output, [])

    def test_unknown_profile_identity_is_logged_and_skipped(self):
        self.source.profile = types.SimpleNamespace(name="Copilot Agents")

        self.deliver()

        self.assertEqual(self.diagnostics[0].code, "profile_identity_unknown")
        self.assertEqual(self.output, [])

    def test_closed_session_is_a_noop(self):
        self.app.sessions.clear()

        self.deliver()

        self.assertEqual(self.output, [])

    def test_returned_session_with_different_uuid_is_skipped(self):
        mismatched = FakeSession(OTHER_ID.upper(), profile=self.profile)
        self.app.sessions = {SOURCE_ID.upper(): mismatched}

        self.deliver()

        self.assertEqual(self.diagnostics[0].code, "source_identity_unknown")
        self.assertEqual(self.output, [])

    def test_waiting_message_uses_source_repo_label_and_exact_osc_bytes(self):
        event = HookEvent("Notification", "/wrong/focused/repo", "permission_prompt", SOURCE_ID)

        self.deliver(event=event)

        self.assertEqual(
            self.output,
            [("/dev/ttys001", b"\x1b]9;Copilot needs your attention: repo|worktree\x07")],
        )

    def test_waiting_message_preserves_utf8_source_label(self):
        self.source.variables["user.repoLabel"] = "répo"

        self.deliver()

        self.assertEqual(
            self.output[0][1],
            b"\x1b]9;Copilot needs your attention: r\xc3\xa9po\x07",
        )

    def test_non_string_repo_label_falls_back_to_safe_source_context(self):
        self.source.variables["user.repoLabel"] = 42

        self.deliver()

        self.assertEqual(self.output[0][1], b"\x1b]9;Copilot needs your attention: repo\x07")

    def test_independent_source_uuid_selects_its_own_tty_and_label(self):
        second = FakeSession(OTHER_ID.upper(), profile=self.profile, tty="/dev/ttys002", repo_label="other")
        self.app.sessions[second.session_id] = second
        event = HookEvent("Notification", "/elsewhere/cwd-name", "permission_prompt", OTHER_ID)

        self.deliver(event=event)

        self.assertEqual(self.app.lookups, [OTHER_ID.upper()] * 3)
        self.assertEqual(
            self.output,
            [("/dev/ttys002", b"\x1b]9;Copilot needs your attention: other\x07")],
        )

    def test_focused_source_suppresses_only_when_application_is_active(self):
        self.app.app_active = True

        self.deliver()

        self.assertEqual(self.output, [])
        self.assertEqual(self.app.refreshes, 1)

    def test_background_or_inactive_application_does_not_suppress(self):
        self.app.app_active = False
        self.app.current_window = FakeWindow("other-window", FakeTab("other-tab", self.source))

        self.deliver()

        self.assertEqual(len(self.output), 1)

    def test_source_in_background_window_does_not_suppress_active_app(self):
        self.app.app_active = True
        self.app.current_window = FakeWindow("other-window", FakeTab("other-tab", self.source))

        self.deliver()

        self.assertEqual(len(self.output), 1)

    def test_unknown_focus_logs_then_delivers(self):
        self.app.app_active = True
        self.app.focus_error = self.iterm.RPCException("private API payload")

        self.deliver()

        self.assertEqual(self.diagnostics[0].code, "focus_unknown")
        self.assertNotIn(
            "private API payload",
            diagnostic_line(self.diagnostics[0].code, self.diagnostics[0]),
        )
        self.assertEqual(len(self.output), 1)

    def test_profile_lookup_failure_is_reported_and_skips_action(self):
        async def fail_profile():
            raise self.iterm.RPCException("private profile payload")

        self.source.async_get_profile = fail_profile

        self.deliver()

        self.assertEqual(self.diagnostics[0].code, "source_profile_unknown")
        self.assertEqual(self.output, [])

    def test_focus_predicate_compares_ids_not_object_identity(self):
        self.app.app_active = True
        self.app.current_window = FakeWindow("window-source", FakeTab("tab-source", self.source))
        self.app.window = FakeWindow("window-source", FakeTab("tab-source", self.source))

        self.deliver()

        self.assertEqual(self.output, [])

    def test_done_action_is_bell_only_even_when_source_is_focused(self):
        self.app.app_active = True

        self.deliver("done", HookEvent("Stop", "/source/repo", None, SOURCE_ID))

        self.assertEqual(self.output, [("/dev/ttys001", b"\x07")])
        self.assertEqual(self.app.refreshes, 0)

    def test_changed_tty_association_is_not_used_after_refresh(self):
        self.source.variables["tty"] = "/dev/ttys002"
        original_refresh = self.app.async_refresh

        async def refresh_then_change():
            await original_refresh()
            self.source.variables["tty"] = "/dev/ttys003"

        self.app.async_refresh = refresh_then_change

        with self.assertRaises(DeliveryError) as raised:
            self.deliver()

        self.assertEqual(raised.exception.code, "source_changed")
        self.assertEqual(self.output, [])

    def test_tty_write_failure_is_bounded_delivery_error(self):
        self.writer_patch.stop()
        self.writer_patch = patch.object(terminal, "write_tty", side_effect=OSError("private path"))
        self.writer_patch.start()
        self.addCleanup(self.writer_patch.stop)

        with self.assertRaises(DeliveryError) as raised:
            self.deliver()

        self.assertEqual(raised.exception.code, "tty_write_failed")

    def test_each_drain_uses_one_connection_and_closes_it(self):
        with terminal.open_sink() as sink:
            sink("done", HookEvent("Stop", None, None, SOURCE_ID))
            sink("done", HookEvent("Stop", None, None, SOURCE_ID))

        self.assertEqual(self.iterm.connect_calls, 1)
        self.assertTrue(self.iterm.connection.closed)

    def test_connection_closes_if_app_lookup_fails(self):
        async def fail_app(_connection):
            raise self.iterm.RPCException("private app response")

        self.iterm.async_get_app = fail_app

        with self.assertRaises(DeliveryError) as raised:
            with terminal.open_sink(report=self.diagnostics.append):
                self.fail("connection should not open without an app")

        self.assertEqual(raised.exception.code, "iterm_connection_failed")
        self.assertTrue(self.iterm.connection.closed)


class TtyTransportTests(unittest.TestCase):
    def test_owned_character_tty_receives_exact_bytes(self):
        master, slave = pty.openpty()
        self.addCleanup(os.close, master)
        self.addCleanup(os.close, slave)
        tty = os.ttyname(slave)
        os.set_blocking(master, False)

        terminal.write_tty(tty, b"\x1b]9;source\x07")

        self.assertEqual(os.read(master, 128), b"\x1b]9;source\x07")

    def test_symlink_tty_is_rejected_before_open(self):
        link_stat = os.stat_result((
            stat.S_IFLNK | 0o777, 1, 0, 1, os.getuid(), os.getgid(), 0, 0, 0, 0,
        ))
        with patch("iterm_notifications.tty.os.lstat", return_value=link_stat):
            with patch("iterm_notifications.tty.os.open") as open_file:
                with self.assertRaises(DeliveryError) as raised:
                    terminal.write_tty("/dev/tty-link", b"\x07")

        self.assertEqual(raised.exception.code, "tty_unsafe")
        open_file.assert_not_called()

    def test_non_tty_and_symlink_paths_are_rejected(self):
        with self.assertRaises(DeliveryError):
            terminal.write_tty(os.devnull, b"\x07")
        with unittest.mock.patch("iterm_notifications.tty.os.open") as open_file:
            with self.assertRaises(DeliveryError):
                terminal.write_tty("/dev/../dev/null", b"\x07")
        open_file.assert_not_called()


if __name__ == "__main__":
    unittest.main()
