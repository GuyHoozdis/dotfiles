import argparse
import contextlib
import importlib.util
import io
import os
import stat
import unittest
from pathlib import Path
from unittest import mock


spec = importlib.util.spec_from_file_location("probe_notifications", Path(__file__).with_name("probe_notifications.py"))
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

SESSION_ID = "12345678-1234-1234-1234-123456789ABC"


class Session:
    session_id = SESSION_ID

    async def async_get_profile(self):
        pass

    async def async_get_variable(self, name):
        pass

    async def async_inject(self, data):
        pass


class App:
    windows = []

    def get_session_by_id(self, session_id, include_buried=True):
        pass


class Api:
    async def async_get_app(self, connection):
        pass


class Profile:
    guid = "local-guid"
    original_guid = probe.PROFILE_GUID
    all_properties = {"BM Growl": True, "Silence Bell": False}


class ProbeTests(unittest.TestCase):
    def test_explicit_complete_arguments_required(self):
        with contextlib.redirect_stderr(io.StringIO()):
            for args in ([], ["--session", SESSION_ID], ["--session", SESSION_ID, "--kind", "done"]):
                with self.subTest(args=args), self.assertRaises(SystemExit):
                    probe.parse_args(args)
        self.assertEqual(probe.parse_args(["--session", SESSION_ID, "--inspect"]).session, SESSION_ID)

    def test_tty_path_rejects_escape_and_symlinks(self):
        for path in ("/dev/../etc/passwd", "/dev/null/../null", "/dev/bad\nname", "/etc/passwd", None):
            with self.subTest(path=path), self.assertRaises(probe.ProbeError):
                probe.validate_tty_path(path)
        with mock.patch.object(probe.os.path, "realpath", autospec=True, return_value="/dev/other"):
            with self.assertRaises(probe.ProbeError):
                probe.validate_tty_path("/dev/link")

    def test_tty_validated_descriptor_gets_one_exact_write(self):
        device = os.stat_result((stat.S_IFCHR | 0o600, 1, 2, 1, os.getuid(), 0, 0, 0, 0, 0))
        with (
            mock.patch.object(probe.os.path, "realpath", autospec=True, return_value="/dev/test"),
            mock.patch.object(probe.os, "lstat", autospec=True, return_value=device),
            mock.patch.object(probe.os, "open", autospec=True, return_value=4) as open_device,
            mock.patch.object(probe.os, "fstat", autospec=True, return_value=device),
            mock.patch.object(probe.os, "isatty", autospec=True, return_value=True),
            mock.patch.object(probe.os, "close", autospec=True) as close,
            mock.patch.object(probe.os, "write", autospec=True, return_value=1) as write,
        ):
            probe.write_tty("/dev/test", probe.PAYLOADS["done"])
            open_device.assert_called_once_with("/dev/test", os.O_WRONLY | os.O_NONBLOCK | os.O_NOCTTY | os.O_NOFOLLOW)
            write.assert_called_once_with(4, b"\x07")
            close.assert_called_once_with(4)

    def test_tty_rejects_descriptor_swap_before_write(self):
        original = os.stat_result((stat.S_IFCHR | 0o600, 1, 2, 1, os.getuid(), 0, 0, 0, 0, 0))
        swapped = os.stat_result((stat.S_IFCHR | 0o600, 3, 2, 1, os.getuid(), 0, 0, 0, 0, 0))
        with (
            mock.patch.object(probe.os.path, "realpath", autospec=True, return_value="/dev/test"),
            mock.patch.object(probe.os, "lstat", autospec=True, return_value=original),
            mock.patch.object(probe.os, "open", autospec=True, return_value=4),
            mock.patch.object(probe.os, "fstat", autospec=True, return_value=swapped),
            mock.patch.object(probe.os, "close", autospec=True) as close,
            mock.patch.object(probe.os, "write", autospec=True) as write,
        ):
            with self.assertRaises(probe.ProbeError):
                probe.write_tty("/dev/test", probe.PAYLOADS["done"])
            write.assert_not_called()
            close.assert_called_once_with(4)


class AsyncProbeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.session = mock.create_autospec(Session, instance=True)
        self.session.session_id = SESSION_ID
        self.profile = mock.create_autospec(Profile, instance=True)
        self.profile.guid = "local-guid"
        self.profile.original_guid = probe.PROFILE_GUID
        self.profile.all_properties = {"BM Growl": True, "Silence Bell": False}
        self.session.async_get_profile.return_value = self.profile
        self.session.async_get_variable.return_value = "/dev/ttys123"
        self.app = mock.create_autospec(App, instance=True)
        self.app.windows = []
        self.app.get_session_by_id.return_value = self.session
        self.api = mock.create_autospec(Api, instance=True)
        self.api.async_get_app.return_value = self.app
        self.args = argparse.Namespace(session=SESSION_ID, inspect=False, transport="api", kind="waiting")

    async def test_original_guid_allows_local_profile_and_injects_once(self):
        with mock.patch.object(probe, "version", autospec=True, return_value="test"):
            result = await probe.probe(object(), self.args, self.api)
        self.session.async_inject.assert_awaited_once_with(b"\x1b]9;Copilot test: waiting for input\x07")
        self.assertEqual(result["status"], "submitted_not_verified")

    async def test_original_guid_takes_precedence_over_matching_current_guid(self):
        self.profile.guid = probe.PROFILE_GUID
        self.profile.original_guid = "different"
        with self.assertRaises(probe.ProbeError):
            await probe.probe(object(), self.args, self.api)
        self.session.async_inject.assert_not_awaited()

    async def test_wrong_session_id_is_rejected_before_profile_or_delivery(self):
        self.session.session_id = "different"
        with self.assertRaises(probe.ProbeError):
            await probe.probe(object(), self.args, self.api)
        self.session.async_get_profile.assert_not_awaited()
        self.session.async_inject.assert_not_awaited()

    async def test_failed_tty_does_not_fall_back_to_injection(self):
        self.args.transport = "tty"
        with (
            mock.patch.object(probe, "version", autospec=True, return_value="test"),
            mock.patch.object(probe, "write_tty", autospec=True, side_effect=probe.ProbeError("failed")),
        ):
            with self.assertRaises(probe.ProbeError):
                await probe.probe(object(), self.args, self.api)
        self.session.async_inject.assert_not_awaited()

    async def test_inspection_reports_missing_keys_without_sending(self):
        self.args.inspect = True
        with mock.patch.object(probe, "version", autospec=True, return_value="test"):
            result = await probe.probe(object(), self.args, self.api)
        self.assertEqual(result["baseline"]["BM Growl"], True)
        self.assertIsNone(result["baseline"]["Send Bell Alert"])
        self.assertIn("Send Bell Alert", result["baseline_unavailable"])
        self.session.async_inject.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
