"""AuditLog 现有行为的锁定测试。"""

import os
import shutil
import tempfile
import threading
import unittest

from auditchain import AuditLog, CorruptLogError
from auditchain.codec import record_digest


class LogTestBase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="auditchain-log-")
        self.path = os.path.join(self.tmpdir, "audit.log")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def write_raw(self, blob):
        with open(self.path, "ab") as handle:
            handle.write(blob)


class TestAppend(LogTestBase):
    def test_seq_starts_at_one_and_grows(self):
        log = AuditLog(self.path)
        self.assertEqual(log.append("login", ts=1)["seq"], 1)
        self.assertEqual(log.append("export", ts=2)["seq"], 2)
        self.assertEqual(log.count(), 2)

    def test_record_keeps_the_fields_it_was_given(self):
        log = AuditLog(self.path)
        record = log.append("punish", actor="wang", detail="扣奖", ts=1700000000)
        self.assertEqual(record["action"], "punish")
        self.assertEqual(record["actor"], "wang")
        self.assertEqual(record["detail"], "扣奖")
        self.assertEqual(record["ts"], 1700000000)
        self.assertEqual(record["seq"], 1)
        self.assertEqual(len(record["digest"]), 64)

    def test_digest_matches_the_content(self):
        log = AuditLog(self.path)
        record = log.append("login", actor="li", ts=5)
        self.assertEqual(record_digest(record), record["digest"])

    def test_default_timestamp_comes_from_the_clock(self):
        log = AuditLog(self.path, clock=lambda: 42.5)
        self.assertEqual(log.append("login")["ts"], 42.5)

    def test_returned_record_is_a_copy(self):
        log = AuditLog(self.path)
        record = log.append("login", ts=1)
        record["action"] = "tampered"
        self.assertEqual(log.last()["action"], "login")
        self.assertEqual(log.read_all()[0]["action"], "login")

    def test_last_is_a_copy_too(self):
        log = AuditLog(self.path)
        log.append("login", ts=1)
        snapshot = log.last()
        snapshot["action"] = "tampered"
        self.assertEqual(log.last()["action"], "login")


class TestRead(LogTestBase):
    def test_read_all_on_missing_file_is_empty_and_creates_nothing(self):
        log = AuditLog(self.path)
        self.assertEqual(log.read_all(), [])
        self.assertIsNone(log.last())
        self.assertEqual(log.count(), 0)
        self.assertFalse(os.path.exists(self.path))

    def test_read_all_returns_records_in_write_order(self):
        log = AuditLog(self.path)
        for name in ("a", "b", "c"):
            log.append(name, ts=1)
        self.assertEqual([r["action"] for r in log.read_all()], ["a", "b", "c"])

    def test_reopen_continues_the_sequence(self):
        log = AuditLog(self.path)
        log.append("login", ts=1)
        log.append("export", ts=2)
        reopened = AuditLog(self.path)
        self.assertEqual(reopened.count(), 2)
        self.assertEqual(reopened.last()["action"], "export")
        self.assertEqual(reopened.append("punish", ts=3)["seq"], 3)
        self.assertEqual([r["seq"] for r in reopened.read_all()], [1, 2, 3])

    def test_torn_tail_is_ignored_on_reopen(self):
        log = AuditLog(self.path)
        log.append("login", ts=1)
        self.write_raw(b'{"seq":2,"act')
        reopened = AuditLog(self.path)
        self.assertEqual(reopened.count(), 1)
        self.assertEqual([r["action"] for r in reopened.read_all()], ["login"])

    def test_corrupt_line_surfaces_as_corrupt_log_error(self):
        log = AuditLog(self.path)
        log.append("login", ts=1)
        self.write_raw(b"garbage\n")
        with self.assertRaises(CorruptLogError):
            log.read_all()


class TestThreads(LogTestBase):
    def test_concurrent_appends_never_reuse_a_seq(self):
        log = AuditLog(self.path)
        seen = []
        seen_lock = threading.Lock()

        def worker(tag):
            own = [log.append("job", actor=tag, ts=1)["seq"] for _ in range(50)]
            with seen_lock:
                seen.extend(own)

        threads = [threading.Thread(target=worker, args=("t%d" % i,)) for i in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(len(seen), 200)
        self.assertEqual(sorted(seen), list(range(1, 201)))
        self.assertEqual(log.count(), 200)
        self.assertEqual(len(log.read_all()), 200)


if __name__ == "__main__":
    unittest.main()
