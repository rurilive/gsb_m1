"""防篡改链、检查点、verify、老日志迁移的测试。"""

import json
import os
import shutil
import tempfile
import threading
import time
import unittest

from auditchain import AuditLog, CorruptLogError
from auditchain.codec import record_digest
from auditchain.log import GENESIS_PREV


class ChainTestBase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="auditchain-chain-")
        self.path = os.path.join(self.tmpdir, "audit.log")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def read_lines(self):
        with open(self.path, "rb") as handle:
            return handle.read().split(b"\n")

    def tamper(self, seq, **changes):
        """改掉第 seq 条的内容写回文件，模拟人手改记录。"""
        lines = self.read_lines()
        record = json.loads(lines[seq - 1].decode("ascii"))
        record.update(changes)
        lines[seq - 1] = json.dumps(
            record, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
        with open(self.path, "wb") as handle:
            handle.write(b"\n".join(lines))


class TestChainLinks(ChainTestBase):
    def test_first_record_points_at_genesis(self):
        log = AuditLog(self.path)
        self.assertEqual(log.append("login", ts=1)["prev"], GENESIS_PREV)

    def test_each_record_carries_previous_digest(self):
        log = AuditLog(self.path)
        first = log.append("a", ts=1)
        second = log.append("b", ts=2)
        third = log.append("c", ts=3)
        self.assertEqual(second["prev"], first["digest"])
        self.assertEqual(third["prev"], second["digest"])

    def test_chain_survives_reopen(self):
        log = AuditLog(self.path)
        last = log.append("a", ts=1)
        reopened = AuditLog(self.path)
        self.assertEqual(reopened.append("b", ts=2)["prev"], last["digest"])


class TestVerify(ChainTestBase):
    def test_empty_log_verifies(self):
        result = AuditLog(self.path).verify()
        self.assertEqual(
            result, {"ok": True, "first_bad": None, "last_good": None, "checked": 0}
        )

    def test_healthy_log_verifies(self):
        log = AuditLog(self.path)
        for i in range(3):
            log.append("a%d" % i, ts=i)
        self.assertEqual(
            log.verify(),
            {"ok": True, "first_bad": None, "last_good": 3, "checked": 3},
        )

    def test_tampered_record_is_named_by_deep_verify(self):
        log = AuditLog(self.path)
        for i in range(5):
            log.append("a%d" % i, ts=i)
        self.tamper(3, detail="手改的")
        result = AuditLog(self.path).verify(deep=True)
        self.assertFalse(result["ok"])
        self.assertEqual(result["first_bad"], 3)
        self.assertEqual(result["last_good"], 2)

    def test_tamper_with_recomputed_digest_caught_at_next_record(self):
        log = AuditLog(self.path)
        for i in range(4):
            log.append("a%d" % i, ts=i)
        lines = self.read_lines()
        record = json.loads(lines[1].decode("ascii"))
        record["detail"] = "手改的"
        record["digest"] = record_digest(record)
        lines[1] = json.dumps(
            record, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
        with open(self.path, "wb") as handle:
            handle.write(b"\n".join(lines))
        result = AuditLog(self.path).verify(deep=True)
        self.assertFalse(result["ok"])
        self.assertEqual(result["first_bad"], 3)

    def test_default_verify_starts_at_latest_checkpoint(self):
        log = AuditLog(self.path, checkpoint_every=10)
        for i in range(25):
            log.append("a%d" % i, ts=i)
        result = log.verify()
        self.assertTrue(result["ok"])
        self.assertEqual(result["checked"], 5)
        self.assertEqual(result["last_good"], 25)

    def test_deep_verify_checks_every_record(self):
        log = AuditLog(self.path, checkpoint_every=10)
        for i in range(25):
            log.append("a%d" % i, ts=i)
        result = log.verify(deep=True)
        self.assertTrue(result["ok"])
        self.assertEqual(result["checked"], 25)

    def test_tamper_before_checkpoint_only_caught_by_deep(self):
        log = AuditLog(self.path, checkpoint_every=10)
        for i in range(25):
            log.append("a%d" % i, ts=i)
        self.tamper(3, detail="手改的")
        self.assertTrue(AuditLog(self.path, checkpoint_every=10).verify()["ok"])
        result = AuditLog(self.path, checkpoint_every=10).verify(deep=True)
        self.assertFalse(result["ok"])
        self.assertEqual(result["first_bad"], 3)

    def test_tamper_after_checkpoint_caught_by_default_verify(self):
        log = AuditLog(self.path, checkpoint_every=10)
        for i in range(25):
            log.append("a%d" % i, ts=i)
        self.tamper(23, detail="手改的")
        result = AuditLog(self.path, checkpoint_every=10).verify()
        self.assertFalse(result["ok"])
        self.assertEqual(result["first_bad"], 23)
        self.assertEqual(result["checked"], 3)


class TestBrokenTails(ChainTestBase):
    def test_torn_tail_does_not_break_verify(self):
        log = AuditLog(self.path)
        for i in range(3):
            log.append("a%d" % i, ts=i)
        with open(self.path, "ab") as handle:
            handle.write(b'{"seq":4,"act')
        result = AuditLog(self.path).verify()
        self.assertTrue(result["ok"])
        self.assertEqual(result["last_good"], 3)
        self.assertEqual(result["checked"], 3)

    def test_truncated_tail_is_reported_with_last_consistent_point(self):
        log = AuditLog(self.path, checkpoint_every=5)
        for i in range(20):
            log.append("a%d" % i, ts=i)
        lines = self.read_lines()[:12]
        with open(self.path, "wb") as handle:
            handle.write(b"\n".join(lines) + b"\n")
        result = AuditLog(self.path, checkpoint_every=5).verify()
        self.assertFalse(result["ok"])
        self.assertEqual(result["first_bad"], 13)
        self.assertEqual(result["last_good"], 12)
        self.assertEqual(result["checked"], 12)

    def test_garbage_line_still_surfaces_as_corrupt_log_error(self):
        log = AuditLog(self.path)
        for i in range(3):
            log.append("a%d" % i, ts=i)
        with open(self.path, "ab") as handle:
            handle.write(b"garbage\n")
        with self.assertRaises(CorruptLogError):
            AuditLog(self.path)

    def test_garbage_written_after_open_is_located_by_verify(self):
        log = AuditLog(self.path)
        for i in range(3):
            log.append("a%d" % i, ts=i)
        with open(self.path, "ab") as handle:
            handle.write(b"garbage\n")
        result = log.verify()
        self.assertFalse(result["ok"])
        self.assertEqual(result["first_bad"], 4)
        self.assertEqual(result["last_good"], 3)


class TestLegacyMigration(ChainTestBase):
    def write_legacy(self, count):
        """按上一版的格式写日志：没有 prev，digest 不覆盖 prev。"""
        with open(self.path, "wb") as handle:
            for seq in range(1, count + 1):
                record = {"seq": seq, "ts": float(seq), "action": "legacy"}
                record["digest"] = record_digest(record)
                blob = json.dumps(
                    record, sort_keys=True, separators=(",", ":"), ensure_ascii=True
                ).encode("ascii")
                handle.write(blob + b"\n")

    def test_legacy_log_opens_and_verifies(self):
        self.write_legacy(3)
        log = AuditLog(self.path)
        self.assertEqual(log.count(), 3)
        self.assertEqual(
            log.verify(deep=True),
            {"ok": True, "first_bad": None, "last_good": 3, "checked": 3},
        )

    def test_migration_is_in_place_and_preserves_content(self):
        self.write_legacy(3)
        log = AuditLog(self.path)
        records = log.read_all()
        self.assertEqual([r["action"] for r in records], ["legacy"] * 3)
        self.assertEqual([r["seq"] for r in records], [1, 2, 3])
        for record in records:
            self.assertIn("prev", record)
        self.assertEqual(records[0]["prev"], GENESIS_PREV)
        self.assertEqual(records[1]["prev"], records[0]["digest"])

    def test_legacy_log_keeps_appending_on_the_chain(self):
        self.write_legacy(3)
        log = AuditLog(self.path)
        fourth = log.append("new", ts=4)
        self.assertEqual(fourth["seq"], 4)
        self.assertEqual(fourth["prev"], log.read_all()[2]["digest"])
        self.assertTrue(log.verify(deep=True)["ok"])

    def test_legacy_torn_tail_is_dropped_by_migration(self):
        self.write_legacy(2)
        with open(self.path, "ab") as handle:
            handle.write(b'{"seq":3,"act')
        log = AuditLog(self.path)
        self.assertEqual(log.count(), 2)
        self.assertTrue(log.verify(deep=True)["ok"])


class TestChainThreads(ChainTestBase):
    def test_concurrent_appends_form_a_single_chain(self):
        log = AuditLog(self.path)

        def worker():
            for _ in range(50):
                log.append("job", ts=1)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        result = log.verify(deep=True)
        self.assertTrue(result["ok"])
        self.assertEqual(result["checked"], 200)
        self.assertEqual(result["last_good"], 200)


class TestPerf(ChainTestBase):
    def test_hundred_thousand_appends_and_verify_under_a_minute(self):
        log = AuditLog(self.path)
        started = time.monotonic()
        for i in range(100000):
            log.append("bulk", actor="perf", ts=i)
        result = log.verify()
        deep = log.verify(deep=True)
        elapsed = time.monotonic() - started
        self.assertTrue(result["ok"])
        self.assertTrue(deep["ok"])
        self.assertEqual(deep["checked"], 100000)
        self.assertLess(elapsed, 60)


if __name__ == "__main__":
    unittest.main()
