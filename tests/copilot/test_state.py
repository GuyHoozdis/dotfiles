import contextlib
import dataclasses
import fcntl
import json
import os
import stat
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "share" / "copilot"))

from iterm_notifications.context import HookEvent
from iterm_notifications import safefs, spool, worker
from iterm_notifications.diagnostics import DiagnosticError
from iterm_notifications.state import (
    FeedbackState, SessionState, apply_record, decode_state, encode_state, reduce_event,
)


SESSION_ID = "12345678-1234-1234-1234-123456789abc"
OTHER_ID = "abcdefab-cdef-abcd-efab-cdefabcdefab"


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


class SessionStateTests(unittest.TestCase):
    def event(self, name, notification_type=None):
        return HookEvent(name, None, notification_type, SESSION_ID)

    def test_replayed_sequences_are_ignored(self):
        state = SessionState(FeedbackState(True, False), 5)
        self.assertEqual(apply_record(state, 5, self.event("SessionStart")), (state, None))
        self.assertEqual(
            apply_record(state, 4, self.event("Notification", "permission_prompt")), (state, None)
        )

    def test_new_sequence_advances_watermark(self):
        self.assertEqual(
            apply_record(SessionState(), 1, self.event("Notification", "permission_prompt")),
            (SessionState(FeedbackState(True, False), 1), "waiting"),
        )

    def test_session_end_clears_flags_but_keeps_watermark(self):
        self.assertEqual(
            apply_record(SessionState(FeedbackState(True, True), 7), 8, self.event("SessionEnd")),
            (SessionState(FeedbackState(), 8), None),
        )

    def test_encoding_round_trips_and_rejects_corruption(self):
        for state in (SessionState(), SessionState(FeedbackState(True, False), 9)):
            with self.subTest(state=state):
                self.assertEqual(decode_state(encode_state(state)), state)
        valid = {"version": 1, "last_seq": 1, "waiting_seen": False, "done_seen": False}
        for bad in (
            b"", b"[]", b"\xff", json.dumps({"version": 1}).encode(),
            json.dumps(valid | {"last_seq": -1}).encode(),
            json.dumps(valid | {"last_seq": True}).encode(),
            json.dumps(valid | {"done_seen": 1}).encode(),
            json.dumps(valid | {"version": 2}).encode(),
            json.dumps(valid | {"extra": 1}).encode(),
        ):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    decode_state(bad)


class RecordingSink:
    def __init__(self, fail=(), spool_=None):
        self.actions = []
        self.opened = 0
        self.fail = set(fail)
        self.spool = spool_
        self.observed = []

    @contextlib.contextmanager
    def open(self):
        self.opened += 1
        yield self.deliver

    def deliver(self, action, event):
        self.actions.append((action, event.source_uuid))
        if self.spool is not None:
            self.observed.append(self.spool.load_state())
        if action in self.fail:
            raise worker.DeliveryError("terminal_write_failed")


class SpoolTestCase(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.environ = {"TMPDIR": directory.name}

    def open(self, source=SESSION_ID):
        opened = spool.Spool.open(source, self.environ)
        self.addCleanup(opened.close)
        return opened

    def session_dir(self, source=SESSION_ID):
        return self.root / "copilot-iterm-status" / source.upper()

    def queue_names(self, source=SESSION_ID):
        return sorted(os.listdir(self.session_dir(source) / "notification-queue"))

    def enqueue(self, opened, name, kind=None, source=SESSION_ID):
        return opened.enqueue(HookEvent(name, "/source", kind, source))

    def drain(self, opened, sink=None):
        sink = sink or RecordingSink()
        diagnostics = []
        self.assertTrue(worker.drain(opened, sink.open, diagnostics.append))
        return sink.actions, [error.code for error in diagnostics]


class QueueTests(SpoolTestCase):
    def test_waiting_then_activity_before_drain_still_delivers_waiting(self):
        opened = self.open()
        self.enqueue(opened, "Notification", "permission_prompt")
        self.enqueue(opened, "PreToolUse")
        self.assertEqual(self.drain(opened), ([("waiting", SESSION_ID)], []))
        self.assertEqual(opened.load_state(), SessionState(FeedbackState(), 2))
        self.assertEqual(self.queue_names(), [])

    def test_layout_is_owner_only_and_leaves_status_files_untouched(self):
        session = self.session_dir()
        (session / "lock").mkdir(parents=True)
        for name, body in (("latest", "1 waiting\n"), ("sent", "0 idle\n"), ("lock/pid", "1\n")):
            (session / name).write_text(body)
        before = {name: (session / name).stat().st_ino for name in ("latest", "sent", "lock/pid")}
        opened = self.open()
        self.enqueue(opened, "Notification", "permission_prompt")
        self.drain(opened)
        for name in ("copilot-iterm-status", f"copilot-iterm-status/{SESSION_ID.upper()}",
                     f"copilot-iterm-status/{SESSION_ID.upper()}/notification-queue"):
            self.assertEqual(stat.S_IMODE((self.root / name).stat().st_mode), 0o700)
        for name in ("notification-state.json", "notification.lock"):
            self.assertEqual(stat.S_IMODE((session / name).stat().st_mode), 0o600)
        self.assertEqual((session / "latest").read_text(), "1 waiting\n")
        self.assertEqual((session / "sent").read_text(), "0 idle\n")
        self.assertEqual((session / "lock/pid").read_text(), "1\n")
        self.assertEqual(
            before, {name: (session / name).stat().st_ino for name in ("latest", "sent", "lock/pid")}
        )

    def test_sessions_are_independent(self):
        first, second = self.open(), self.open(OTHER_ID)
        self.enqueue(first, "Notification", "permission_prompt")
        self.enqueue(second, "Notification", "elicitation_dialog", OTHER_ID)
        self.assertEqual(self.drain(first)[0], [("waiting", SESSION_ID)])
        self.assertEqual(self.queue_names(OTHER_ID), ["00000000000000000001.event"])
        self.assertEqual(self.drain(second)[0], [("waiting", OTHER_ID)])
        self.assertEqual(second.load_state(), SessionState(FeedbackState(True, False), 1))

    def test_repeated_events_deduplicate_until_activity(self):
        opened = self.open()
        for name, kind in (
            ("Notification", "permission_prompt"), ("Notification", "permission_prompt"),
            ("Stop", None), ("Stop", None), ("PreToolUse", None),
            ("Notification", "elicitation_dialog"),
        ):
            self.enqueue(opened, name, kind)
        self.assertEqual(
            [action for action, _ in self.drain(opened)[0]], ["waiting", "done", "waiting"]
        )

    def test_sequence_survives_full_drains_and_session_end(self):
        opened = self.open()
        self.assertEqual(self.enqueue(opened, "Notification", "permission_prompt"), 1)
        self.assertEqual(self.enqueue(opened, "SessionEnd"), 2)
        self.drain(opened)
        self.assertEqual(self.enqueue(opened, "Notification", "permission_prompt"), 3)
        self.assertEqual(self.drain(opened)[0], [("waiting", SESSION_ID)])
        self.assertEqual(opened.load_state(), SessionState(FeedbackState(True, False), 3))

    def test_missing_or_corrupt_counter_never_reuses_processed_sequences(self):
        opened = self.open()
        for _ in range(3):
            self.enqueue(opened, "PreToolUse")
        self.drain(opened)
        counter = self.session_dir() / "notification-sequence"
        counter.unlink()
        self.assertEqual(self.enqueue(opened, "PreToolUse"), 4)
        counter.write_text("garbage")
        self.assertEqual(self.enqueue(opened, "PreToolUse"), 5)

    def test_concurrent_producers_allocate_unique_ordered_sequences(self):
        barrier = threading.Barrier(8)
        results = []
        lock = threading.Lock()

        def produce():
            with spool.Spool.open(SESSION_ID, self.environ) as opened:
                barrier.wait(timeout=10)
                for _ in range(5):
                    seq = self.enqueue(opened, "PreToolUse")
                    with lock:
                        results.append(seq)

        threads = [threading.Thread(target=produce) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
            self.assertFalse(thread.is_alive())
        self.assertEqual(sorted(results), list(range(1, 41)))
        self.assertEqual(self.queue_names(), [f"{seq:020d}.event" for seq in range(1, 41)])

    def test_interrupted_publication_is_never_read(self):
        opened = self.open()
        queue = self.session_dir() / "notification-queue"
        (queue / ".00000000000000000009.event.1.ab.tmp").write_text("partial")
        real_replace = os.replace

        def fail_record(source, target, **kwargs):
            if str(target).endswith(".event"):
                raise OSError("disk full")
            return real_replace(source, target, **kwargs)

        with mock.patch.object(spool.os, "replace", side_effect=fail_record):
            with self.assertRaises(spool.SpoolError) as raised:
                self.enqueue(opened, "Notification", "permission_prompt")
        self.assertEqual(raised.exception.code, "queue_publish_failed")
        self.assertEqual(self.queue_names(), [".00000000000000000009.event.1.ab.tmp"])
        self.enqueue(opened, "Stop")
        self.assertEqual(self.drain(opened), ([("done", SESSION_ID)], []))
        self.assertEqual(self.queue_names(), [".00000000000000000009.event.1.ab.tmp"])

    def test_corrupt_published_record_is_discarded_with_payload_free_diagnostic(self):
        opened = self.open()
        queue = self.session_dir() / "notification-queue"
        (queue / "00000000000000000001.event").write_text('{"prompt": "private secret"')
        self.assertEqual(self.enqueue(opened, "Notification", "permission_prompt"), 2)
        sink = RecordingSink()
        diagnostics = []
        worker.drain(opened, sink.open, diagnostics.append)
        self.assertEqual(sink.actions, [("waiting", SESSION_ID)])
        self.assertEqual([error.code for error in diagnostics], ["record_corrupt"])
        self.assertNotIn("private", repr(diagnostics[0].args))
        self.assertEqual(self.queue_names(), [])
        self.assertEqual(opened.load_state().last_seq, 2)

    def test_wrongly_typed_record_fields_are_discarded_and_draining_continues(self):
        valid = {"version": 1, "seq": 1, "event": "Stop", "cwd": None,
                 "notification_type": None, "source_uuid": SESSION_ID}
        for field, value in (
            ("event", []), ("event", {}), ("event", 1), ("version", []), ("seq", "1"),
            ("seq", True), ("cwd", []), ("notification_type", {}), ("source_uuid", []),
            ("source_uuid", {}),
        ):
            with self.subTest(field=field, value=value):
                with tempfile.TemporaryDirectory() as directory:
                    opened = spool.Spool.open(SESSION_ID, {"TMPDIR": directory})
                    self.addCleanup(opened.close)
                    queue = Path(directory) / "copilot-iterm-status" / SESSION_ID.upper() / "notification-queue"
                    (queue / "00000000000000000001.event").write_text(json.dumps(valid | {field: value}))
                    self.enqueue(opened, "Notification", "permission_prompt")
                    self.assertEqual(
                        self.drain(opened), ([("waiting", SESSION_ID)], ["record_corrupt"])
                    )
                    self.assertEqual(os.listdir(queue), [])

    def test_event_for_another_session_is_rejected(self):
        opened = self.open()
        with self.assertRaises(spool.SpoolError) as raised:
            self.enqueue(opened, "Stop", source=OTHER_ID)
        self.assertEqual(raised.exception.code, "source_mismatch")

    def test_replay_after_delivery_before_removal_does_not_repeat(self):
        opened = self.open()
        self.enqueue(opened, "Notification", "permission_prompt")
        with opened.worker_lock():
            opened.save_state(SessionState(FeedbackState(True, False), 1))
        self.assertEqual(self.drain(opened), ([], []))
        self.assertEqual(self.queue_names(), [])

    def test_old_lifecycle_replay_does_not_rearm_later_flags(self):
        opened = self.open()
        self.enqueue(opened, "SessionStart")
        self.enqueue(opened, "Notification", "permission_prompt")
        self.enqueue(opened, "Notification", "permission_prompt")
        with opened.worker_lock():
            opened.save_state(SessionState(FeedbackState(True, False), 2))
        self.assertEqual(self.drain(opened), ([], []))
        self.assertEqual(opened.load_state(), SessionState(FeedbackState(True, False), 3))

    def test_corrupt_replayed_record_never_lowers_watermark(self):
        opened = self.open()
        (self.session_dir() / "notification-queue" / "00000000000000000001.event").write_text("{")
        with opened.worker_lock():
            opened.save_state(SessionState(FeedbackState(True, False), 2))
        self.assertEqual(self.drain(opened), ([], []))
        self.assertEqual(opened.load_state(), SessionState(FeedbackState(True, False), 2))
        self.assertEqual(self.queue_names(), [])

    def test_observed_state_is_persisted_before_action(self):
        opened = self.open()
        self.enqueue(opened, "PreToolUse")
        self.enqueue(opened, "Notification", "permission_prompt")
        sink = RecordingSink(spool_=opened)
        self.drain(opened, sink)
        self.assertEqual(sink.observed, [SessionState(FeedbackState(True, False), 2)])

    def test_failed_action_is_logged_without_retry_until_activity(self):
        opened = self.open()
        sink = RecordingSink(fail={"waiting"})
        self.enqueue(opened, "Notification", "permission_prompt")
        self.enqueue(opened, "Notification", "permission_prompt")
        self.assertEqual(self.drain(opened, sink), ([("waiting", SESSION_ID)], ["terminal_write_failed"]))
        self.enqueue(opened, "PostToolUse")
        self.enqueue(opened, "Notification", "permission_prompt")
        self.drain(opened, sink)
        self.assertEqual(len(sink.actions), 2)

    def test_sink_opens_lazily_once_per_drain(self):
        opened = self.open()
        sink = RecordingSink()
        self.enqueue(opened, "PreToolUse")
        self.drain(opened, sink)
        self.assertEqual(sink.opened, 0)
        self.enqueue(opened, "Notification", "permission_prompt")
        self.enqueue(opened, "Stop")
        self.drain(opened, sink)
        self.assertEqual(sink.opened, 1)

    def test_sink_close_failure_is_reported_after_queue_is_processed(self):
        opened = self.open()
        self.enqueue(opened, "Notification", "permission_prompt")

        @contextlib.contextmanager
        def failing_close():
            yield lambda action, event: None
            raise worker.DeliveryError("terminal_close_failed")

        diagnostics = []
        self.assertTrue(worker.drain(opened, failing_close, diagnostics.append))
        self.assertEqual([error.code for error in diagnostics], ["terminal_close_failed"])
        self.assertEqual(self.queue_names(), [])

    def test_unavailable_terminal_adapter_is_explicit(self):
        opened = self.open()
        self.enqueue(opened, "Notification", "permission_prompt")
        diagnostics = []
        worker.drain(opened, worker.open_unavailable_sink, diagnostics.append)
        self.assertEqual([error.code for error in diagnostics], ["terminal_adapter_unavailable"])
        self.assertEqual(opened.load_state().feedback, FeedbackState(True, False))

    def test_corrupt_state_is_diagnosed_and_reset(self):
        opened = self.open()
        (self.session_dir() / "notification-state.json").write_text("{")
        self.enqueue(opened, "Stop")
        self.assertEqual(self.drain(opened), ([("done", SESSION_ID)], ["state_corrupt"]))


class LockingTests(SpoolTestCase):
    def test_producer_arriving_after_empty_check_before_release_is_drained(self):
        holder = self.open()
        empty_seen = threading.Event()
        release = threading.Event()
        real_pending = holder.pending

        def pause_when_empty():
            seqs = real_pending()
            if not seqs:
                empty_seen.set()
                self.assertTrue(release.wait(timeout=10))
            return seqs

        holder_sink, contender_sink = RecordingSink(), RecordingSink()
        lock = self.session_dir() / "notification.lock"
        inode = lock.stat().st_ino
        with mock.patch.object(holder, "pending", side_effect=pause_when_empty):
            first = threading.Thread(target=worker.drain, args=(holder, holder_sink.open, list().append))
            first.start()
            self.assertTrue(empty_seen.wait(timeout=10))
            producer = self.open()
            self.enqueue(producer, "Notification", "permission_prompt")
            contender = threading.Thread(
                target=worker.drain, args=(producer, contender_sink.open, list().append)
            )
            contender.start()
            self.assertEqual(self.queue_names(), ["00000000000000000001.event"])
            release.set()
            first.join(timeout=10)
            contender.join(timeout=10)
        self.assertFalse(first.is_alive())
        self.assertFalse(contender.is_alive())
        self.assertEqual(holder_sink.actions, [])
        self.assertEqual(contender_sink.actions, [("waiting", SESSION_ID)])
        self.assertEqual(self.queue_names(), [])
        self.assertEqual(lock.stat().st_ino, inode)

    def test_stale_worker_metadata_does_not_block_and_lock_inode_is_kept(self):
        opened = self.open()
        lock = self.session_dir() / "notification.lock"
        lock.write_text("99999999\n")
        os.utime(lock, (0, 0))
        inode = lock.stat().st_ino
        self.enqueue(opened, "Stop")
        self.assertEqual(self.drain(opened)[0], [("done", SESSION_ID)])
        self.assertEqual(lock.stat().st_ino, inode)
        self.assertEqual(lock.read_text(), f"{os.getpid()}\n")

    def test_enqueue_lock_wait_is_bounded(self):
        self.assertLess(spool.ENQUEUE_TIMEOUT, 5)
        opened = self.open()
        with open(self.session_dir() / "notification-enqueue.lock", "rb") as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            with mock.patch.object(spool, "ENQUEUE_TIMEOUT", 0.05):
                with self.assertRaises(spool.SpoolError) as raised:
                    self.enqueue(opened, "Stop")
        self.assertEqual(raised.exception.code, "enqueue_lock_timeout")
        self.assertEqual(self.queue_names(), [])

    def test_log_keeps_newest_bytes_at_line_boundary(self):
        opened = self.open()
        log = self.session_dir() / "notification-errors.log"
        log.write_text("".join(f'{{"old": {index}}}\n' for index in range(8000)))
        with self.assertRaises(RuntimeError):
            opened.append_log(DiagnosticError("outside_lock"))
        with opened.worker_lock():
            opened.append_log(DiagnosticError("newest_code"))
        data = log.read_bytes()
        self.assertLessEqual(len(data), 64 * 1024)
        lines = data.decode().splitlines()
        self.assertEqual(json.loads(lines[-1])["code"], "newest_code")
        self.assertEqual(json.loads(lines[-1])["error"], "DiagnosticError")
        for line in lines:
            json.loads(line)
        self.assertEqual(stat.S_IMODE(log.stat().st_mode), 0o600)


class SafetyTests(SpoolTestCase):
    def test_atomic_publication_syncs_directory_after_rename(self):
        opened = self.open()
        calls = []
        real_replace, real_fsync = os.replace, os.fsync

        def record_replace(source, target, **kwargs):
            calls.append(("replace", target, kwargs["dst_dir_fd"]))
            return real_replace(source, target, **kwargs)

        def record_fsync(fd):
            calls.append(("fsync", fd))
            return real_fsync(fd)

        with mock.patch.object(safefs.os, "replace", side_effect=record_replace), \
                mock.patch.object(safefs.os, "fsync", side_effect=record_fsync):
            self.enqueue(opened, "Stop")
        renames = [index for index, call in enumerate(calls) if call[0] == "replace"]
        self.assertEqual([calls[index][1] for index in renames],
                         ["notification-sequence", "00000000000000000001.event"])
        for index in renames:
            self.assertEqual(calls[index + 1], ("fsync", calls[index][2]))

    def test_invalid_uuid_is_rejected_before_any_path_is_created(self):
        for bad in ("", "../" + SESSION_ID, SESSION_ID + "/..", "w0:" + SESSION_ID,
                    SESSION_ID.replace("-", ""), SESSION_ID + "\n"):
            with self.subTest(bad=bad):
                with self.assertRaises(spool.SpoolError) as raised:
                    spool.Spool.open(bad, self.environ)
                self.assertEqual(raised.exception.code, "invalid_source_uuid")
        self.assertEqual(os.listdir(self.root), [])

    def test_symlinked_state_paths_are_rejected(self):
        upper = SESSION_ID.upper()
        for relative in ("copilot-iterm-status", f"copilot-iterm-status/{upper}",
                         f"copilot-iterm-status/{upper}/notification-queue",
                         f"copilot-iterm-status/{upper}/notification.lock",
                         f"copilot-iterm-status/{upper}/notification-enqueue.lock"):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                target = root / "target"
                target.mkdir()
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.symlink_to(target)
                with self.assertRaises(spool.SpoolError) as raised:
                    spool.Spool.open(SESSION_ID, {"TMPDIR": directory})
                self.assertEqual(raised.exception.code, "spool_unsafe")
                self.assertEqual(os.listdir(target), [])

    def test_symlinked_state_and_log_files_are_rejected(self):
        target = self.root / "target"
        target.write_text("keep")
        opened = self.open()
        session = self.session_dir()
        (session / "notification-state.json").symlink_to(target)
        with self.assertRaises(spool.SpoolError) as raised:
            opened.load_state()
        self.assertEqual(raised.exception.code, "spool_unsafe")
        (session / "notification-errors.log").symlink_to(target)
        with opened.worker_lock(), self.assertRaises(spool.SpoolError) as raised:
            opened.append_log(DiagnosticError("any_code"))
        self.assertEqual(raised.exception.code, "spool_unsafe")
        self.assertEqual(target.read_text(), "keep")

    def test_loose_owned_directories_are_tightened(self):
        session = self.session_dir()
        session.mkdir(parents=True)
        session.chmod(0o777)
        self.open()
        self.assertEqual(stat.S_IMODE(session.stat().st_mode), 0o700)

    def test_foreign_owner_is_rejected(self):
        with mock.patch.object(spool.os, "geteuid", return_value=os.geteuid() + 1):
            with self.assertRaises(spool.SpoolError) as raised:
                spool.Spool.open(SESSION_ID, self.environ)
        self.assertEqual(raised.exception.code, "spool_unsafe")

    def test_hard_linked_lock_is_rejected(self):
        session = self.session_dir()
        session.mkdir(parents=True)
        outside = self.root / "outside"
        outside.write_text("")
        os.link(outside, session / "notification.lock")
        with self.assertRaises(spool.SpoolError) as raised:
            spool.Spool.open(SESSION_ID, self.environ)
        self.assertEqual(raised.exception.code, "spool_unsafe")


if __name__ == "__main__":
    unittest.main()
