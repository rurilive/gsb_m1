"""防篡改链、检查点与 verify 的行为测试。"""

import json
import os
import shutil
import tempfile
import threading
import time
import unittest

from auditchain import AuditLog
from auditchain.codec import encode_line, record_digest
from auditchain.log import CHAIN_FIELD, GENESIS_PREV


class ChainTestBase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="auditchain-chain-")
        self.path = os.path.join(self.tmpdir, "audit.log")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def fill(self, log, count):
        for i in range(count):
            log.append("job", actor="t", detail="d%d" % i, ts=1000 + i)

    def read_lines(self):
        with open(self.path, "rb") as handle:
            return handle.read().splitlines()

    def rewrite_record(self, seq, **changes):
        """把第 seq 条记录改掉再整份写回，模拟被人手动编辑。"""
        lines = self.read_lines()
        record = json.loads(lines[seq - 1].decode("ascii"))
        record.update(changes)
        lines[seq - 1] = json.dumps(
            record, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
        with open(self.path, "wb") as handle:
            handle.write(b"\n".join(lines) + b"\n")

    def write_raw(self, blob):
        with open(self.path, "ab") as handle:
            handle.write(blob)


class TestChainFields(ChainTestBase):
    def test_every_record_points_at_the_previous_digest(self):
        log = AuditLog(self.path)
        first = log.append("a", ts=1)
        second = log.append("b", ts=2)
        third = log.append("c", ts=3)
        self.assertEqual(first[CHAIN_FIELD], GENESIS_PREV)
        self.assertEqual(second[CHAIN_FIELD], first["digest"])
        self.assertEqual(third[CHAIN_FIELD], second["digest"])

    def test_digest_still_matches_content_with_chain_field(self):
        log = AuditLog(self.path)
        record = log.append("a", ts=1)
        self.assertEqual(record_digest(record), record["digest"])

    def test_chain_survives_reopen(self):
        log = AuditLog(self.path)
        self.fill(log, 3)
        last_digest = log.last()["digest"]
        reopened = AuditLog(self.path)
        self.assertEqual(reopened.append("d", ts=4)[CHAIN_FIELD], last_digest)


class TestVerifyClean(ChainTestBase):
    def test_empty_log_is_ok(self):
        log = AuditLog(self.path)
        self.assertEqual(
            log.verify(),
            {"ok": True, "first_bad": None, "last_good": None, "checked": 0},
        )

    def test_clean_log_verifies_ok(self):
        log = AuditLog(self.path)
        self.fill(log, 5)
        for result in (log.verify(), log.verify(deep=True)):
            self.assertEqual(
                result,
                {"ok": True, "first_bad": None, "last_good": 5, "checked": 5},
            )

    def test_result_has_exactly_the_four_keys(self):
        log = AuditLog(self.path)
        self.fill(log, 3)
        self.assertEqual(
            set(log.verify()), {"ok", "first_bad", "last_good", "checked"}
        )


class TestVerifyTamper(ChainTestBase):
    def test_deep_verify_reports_the_tampered_seq(self):
        log = AuditLog(self.path)
        self.fill(log, 10)
        self.rewrite_record(5, detail="改过的处罚")
        result = log.verify(deep=True)
        self.assertFalse(result["ok"])
        self.assertEqual(result["first_bad"], 5)
        self.assertEqual(result["last_good"], 4)
        self.assertEqual(result["checked"], 5)

    def test_tampered_digest_field_itself_is_caught(self):
        log = AuditLog(self.path)
        self.fill(log, 6)
        self.rewrite_record(3, digest="0" * 64)
        result = log.verify(deep=True)
        self.assertFalse(result["ok"])
        self.assertEqual(result["first_bad"], 3)

    def test_deleted_record_breaks_the_chain(self):
        log = AuditLog(self.path)
        self.fill(log, 8)
        lines = self.read_lines()
        del lines[4]  # 删掉第 5 条
        with open(self.path, "wb") as handle:
            handle.write(b"\n".join(lines) + b"\n")
        result = log.verify(deep=True)
        self.assertFalse(result["ok"])
        self.assertEqual(result["first_bad"], 6)
        self.assertEqual(result["last_good"], 4)

    def test_corrupt_line_in_the_middle_is_reported_not_raised(self):
        log = AuditLog(self.path)
        self.fill(log, 5)
        self.write_raw(b"garbage\n")
        result = log.verify()
        self.assertFalse(result["ok"])
        self.assertEqual(result["first_bad"], 6)
        self.assertEqual(result["last_good"], 5)
        self.assertEqual(result["checked"], 5)


class TestCheckpoints(ChainTestBase):
    def test_checkpoint_file_is_written_every_interval(self):
        log = AuditLog(self.path, checkpoint_interval=10)
        self.fill(log, 25)
        with open(self.path + ".chk", "rb") as handle:
            points = [json.loads(line) for line in handle.read().splitlines()]
        self.assertEqual([p["seq"] for p in points], [10, 20])

    def test_shallow_verify_starts_at_the_latest_checkpoint(self):
        log = AuditLog(self.path, checkpoint_interval=10)
        self.fill(log, 25)
        result = log.verify()
        self.assertTrue(result["ok"])
        self.assertEqual(result["last_good"], 25)
        self.assertEqual(result["checked"], 6)  # 锚点 1 条 + 检查点之后 5 条
        deep = log.verify(deep=True)
        self.assertEqual(deep["checked"], 25)

    def test_shallow_verify_catches_tamper_after_the_checkpoint(self):
        log = AuditLog(self.path, checkpoint_interval=10)
        self.fill(log, 25)
        self.rewrite_record(23, detail="x")
        result = log.verify()
        self.assertFalse(result["ok"])
        self.assertEqual(result["first_bad"], 23)
        self.assertEqual(result["last_good"], 22)

    def test_shallow_trusts_the_checkpoint_deep_does_not(self):
        log = AuditLog(self.path, checkpoint_interval=10)
        self.fill(log, 25)
        # 等长改写，不动后面记录的偏移，检查点本身仍然对得上
        self.rewrite_record(5, detail="xx")
        self.assertTrue(log.verify()["ok"])
        deep = log.verify(deep=True)
        self.assertFalse(deep["ok"])
        self.assertEqual(deep["first_bad"], 5)

    def test_tampered_checkpoint_record_falls_back_to_full_scan(self):
        log = AuditLog(self.path, checkpoint_interval=10)
        self.fill(log, 25)
        self.rewrite_record(20, detail="x")
        result = log.verify()
        self.assertFalse(result["ok"])
        self.assertEqual(result["first_bad"], 20)
        self.assertEqual(result["checked"], 20)  # 核到第一条坏记录就停

    def test_missing_checkpoint_file_means_full_scan(self):
        log = AuditLog(self.path, checkpoint_interval=10)
        self.fill(log, 25)
        os.remove(self.path + ".chk")
        result = log.verify()
        self.assertTrue(result["ok"])
        self.assertEqual(result["checked"], 25)


class TestBrokenTail(ChainTestBase):
    def test_half_written_tail_does_not_fail_verify(self):
        log = AuditLog(self.path)
        self.fill(log, 5)
        self.write_raw(b'{"seq":6,"act')
        result = log.verify(deep=True)
        self.assertEqual(
            result,
            {"ok": True, "first_bad": None, "last_good": 5, "checked": 5},
        )

    def test_truncated_tail_reports_the_last_consistent_point(self):
        log = AuditLog(self.path)
        self.fill(log, 10)
        lines = self.read_lines()
        with open(self.path, "wb") as handle:
            handle.write(b"\n".join(lines[:6]) + b"\n")
        result = AuditLog(self.path).verify(deep=True)
        self.assertEqual(
            result,
            {"ok": True, "first_bad": None, "last_good": 6, "checked": 6},
        )

    def test_reopen_drops_the_torn_tail_and_appends_cleanly(self):
        log = AuditLog(self.path)
        self.fill(log, 3)
        self.write_raw(b'{"seq":4,"act')
        reopened = AuditLog(self.path)
        reopened.append("d", ts=4)
        result = reopened.verify(deep=True)
        self.assertTrue(result["ok"])
        self.assertEqual(result["last_good"], 4)


class TestLegacyLog(ChainTestBase):
    def write_legacy(self, count):
        """按上一版的格式写记录：没有链字段，摘要只覆盖内容。"""
        for i in range(count):
            record = {
                "seq": i + 1,
                "ts": float(1000 + i),
                "action": "legacy",
                "actor": "old",
                "detail": "d%d" % i,
            }
            record["digest"] = record_digest(record)
            self.write_raw(encode_line(record))

    def test_legacy_log_opens_and_gets_chained_in_place(self):
        self.write_legacy(4)
        log = AuditLog(self.path)
        records = log.read_all()
        self.assertEqual(len(records), 4)
        self.assertEqual(records[0][CHAIN_FIELD], GENESIS_PREV)
        self.assertEqual(records[0]["action"], "legacy")
        self.assertEqual(records[0]["actor"], "old")
        result = log.verify(deep=True)
        self.assertTrue(result["ok"])
        self.assertEqual(result["checked"], 4)

    def test_legacy_log_keeps_appending_on_the_new_chain(self):
        self.write_legacy(3)
        log = AuditLog(self.path)
        record = log.append("new", ts=2000)
        self.assertEqual(record["seq"], 4)
        self.assertEqual(record[CHAIN_FIELD], log.read_all()[2]["digest"])
        self.assertTrue(log.verify(deep=True)["ok"])

    def test_legacy_backfill_rebuilds_checkpoints(self):
        self.write_legacy(15)
        log = AuditLog(self.path, checkpoint_interval=10)
        self.assertTrue(os.path.exists(self.path + ".chk"))
        result = log.verify()
        self.assertTrue(result["ok"])
        self.assertEqual(result["checked"], 6)


class TestConcurrentChain(ChainTestBase):
    def test_concurrent_appends_form_a_single_chain(self):
        log = AuditLog(self.path)

        def worker(tag):
            for _ in range(50):
                log.append("job", actor=tag, ts=1)

        threads = [threading.Thread(target=worker, args=("t%d" % i,)) for i in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        records = log.read_all()
        self.assertEqual([r["seq"] for r in records], list(range(1, 201)))
        for left, right in zip(records, records[1:]):
            self.assertEqual(right[CHAIN_FIELD], left["digest"])
        result = log.verify(deep=True)
        self.assertTrue(result["ok"])
        self.assertEqual(result["checked"], 200)


class TestPerformance(ChainTestBase):
    def test_hundred_thousand_appends_and_verify_within_a_minute(self):
        log = AuditLog(self.path)
        started = time.monotonic()
        for i in range(100000):
            log.append("job", actor="bulk", detail="n%d" % i, ts=1000 + i)
        deep = log.verify(deep=True)
        shallow = log.verify()
        elapsed = time.monotonic() - started
        self.assertTrue(deep["ok"])
        self.assertEqual(deep["checked"], 100000)
        self.assertTrue(shallow["ok"])
        self.assertLess(shallow["checked"], 100000)
        self.assertLess(elapsed, 60)


if __name__ == "__main__":
    unittest.main()
