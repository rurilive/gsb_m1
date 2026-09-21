"""防篡改链、检查点、verify 与老日志迁移的测试。"""

import json
import os
import shutil
import tempfile
import threading
import time
import unittest

from auditchain import AuditLog
from auditchain.codec import PREV_FIELD, encode_line, record_digest


class ChainTestBase(unittest.TestCase):
    every = 5

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="auditchain-chain-")
        self.path = os.path.join(self.tmpdir, "audit.log")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def open(self, every=None):
        return AuditLog(self.path, checkpoint_every=self.every if every is None else every)

    def fill(self, count, every=None):
        log = self.open(every)
        for seq in range(1, count + 1):
            log.append("act%d" % seq, actor="u", detail="d", ts=float(seq))
        return log

    def raw_lines(self):
        with open(self.path, "rb") as handle:
            return handle.read().splitlines(keepends=True)

    def write_lines(self, lines):
        with open(self.path, "wb") as handle:
            handle.writelines(lines)

    def edit_record(self, index, **changes):
        """手改落盘文件里第 index 行（0 基，即序号 index+1），保留旧 digest。

        模拟真实篡改：只动手改字段，不重算摘要，也不补后面的链。
        """
        lines = self.raw_lines()
        record = json.loads(lines[index])
        stale_digest = record["digest"]
        record.update(changes)
        record["digest"] = stale_digest
        lines[index] = encode_line(record)
        self.write_lines(lines)

    def truncate_records(self, count):
        """把文件物理截断到只剩前 count 条完整记录。"""
        lines = self.raw_lines()
        self.write_lines(lines[:count])

    def append_raw(self, blob):
        with open(self.path, "ab") as handle:
            handle.write(blob)

    def write_legacy(self, count):
        """按上一版格式（没有链字段）写一份老日志。"""
        with open(self.path, "wb") as handle:
            for seq in range(1, count + 1):
                record = {
                    "seq": seq,
                    "ts": float(seq),
                    "action": "old%d" % seq,
                    "actor": "u",
                    "detail": "d",
                }
                record["digest"] = record_digest(record)
                handle.write(encode_line(record))


class TestChainAppend(ChainTestBase):
    def test_first_record_points_at_empty_prev(self):
        log = self.fill(1)
        record = log.read_all()[0]
        self.assertEqual(record[PREV_FIELD], "")

    def test_each_record_points_at_previous_digest(self):
        log = self.fill(3)
        records = log.read_all()
        self.assertEqual(records[1][PREV_FIELD], records[0]["digest"])
        self.assertEqual(records[2][PREV_FIELD], records[1]["digest"])

    def test_digest_covers_prev(self):
        log = self.fill(2)
        records = log.read_all()
        changed = dict(records[1])
        changed[PREV_FIELD] = "deadbeef"
        self.assertNotEqual(record_digest(changed), records[1]["digest"])


class TestVerifyClean(ChainTestBase):
    def test_empty_log_verifies_clean(self):
        log = self.open()
        self.assertEqual(
            log.verify(),
            {"ok": True, "first_bad": None, "last_good": None, "checked": 0},
        )
        self.assertEqual(
            log.verify(deep=True),
            {"ok": True, "first_bad": None, "last_good": None, "checked": 0},
        )

    def test_clean_log_passes_both_modes(self):
        log = self.fill(12)
        shallow = log.verify()
        deep = log.verify(deep=True)
        self.assertTrue(shallow["ok"])
        self.assertEqual(shallow["last_good"], 12)
        self.assertEqual(shallow["first_bad"], None)
        self.assertEqual(shallow["checked"], 3)
        self.assertTrue(deep["ok"])
        self.assertEqual(deep["last_good"], 12)
        self.assertEqual(deep["checked"], 12)

    def test_shallow_starts_at_latest_checkpoint(self):
        log = self.fill(10)
        result = log.verify()
        self.assertTrue(result["ok"])
        self.assertEqual(result["checked"], 1)

    def test_no_checkpoint_means_full_scan(self):
        log = self.fill(3)
        self.assertEqual(log.verify()["checked"], 3)


class TestVerifyTamper(ChainTestBase):
    def test_tampered_record_after_checkpoint_is_the_first_bad(self):
        self.fill(12)
        self.edit_record(10, action="HACK")
        log = self.open()
        shallow = log.verify()
        deep = log.verify(deep=True)
        self.assertFalse(shallow["ok"])
        self.assertEqual((shallow["first_bad"], shallow["last_good"]), (11, 10))
        self.assertEqual(shallow["checked"], 3)
        self.assertFalse(deep["ok"])
        self.assertEqual((deep["first_bad"], deep["last_good"]), (11, 10))
        self.assertEqual(deep["checked"], 12)

    def test_tampered_record_before_checkpoint_needs_deep(self):
        self.fill(12)
        self.edit_record(1, action="HACK")
        log = self.open()
        shallow = log.verify()
        self.assertTrue(shallow["ok"])
        self.assertEqual(shallow["checked"], 3)
        deep = log.verify(deep=True)
        self.assertFalse(deep["ok"])
        self.assertEqual(deep["first_bad"], 2)
        self.assertEqual(deep["last_good"], 1)
        self.assertEqual(deep["checked"], 12)

    def test_tampered_genesis_is_record_one(self):
        self.fill(12)
        self.edit_record(0, action="HACK")
        log = self.open()
        deep = log.verify(deep=True)
        self.assertFalse(deep["ok"])
        self.assertEqual(deep["first_bad"], 1)
        self.assertIsNone(deep["last_good"])

    def test_retargeted_prev_without_rehash_is_caught(self):
        self.fill(12)
        self.edit_record(11, **{PREV_FIELD: "0" * 64})
        log = self.open()
        self.assertEqual(log.verify(deep=True)["first_bad"], 12)

    def test_rehash_without_touching_checkpoint_is_caught_by_deep(self):
        """改第 3 条并重算日志里整条链，但旁路检查点没动，deep 认得。

        无密钥哈希链识破不了"连检查点一起伪造"的完全重写，那要靠
        外部锚点；只动日志文件时，固化的检查点就是外部对照点。
        """
        self.fill(12)
        lines = self.raw_lines()
        records = [json.loads(line) for line in lines]
        records[2]["action"] = "HACK"
        prev_digest = ""
        for index, record in enumerate(records):
            record[PREV_FIELD] = prev_digest
            record["digest"] = record_digest(record)
            prev_digest = record["digest"]
            lines[index] = encode_line(record)
        self.write_lines(lines)
        log = self.open()
        deep = log.verify(deep=True)
        self.assertFalse(deep["ok"])
        self.assertEqual(deep["first_bad"], 5)
        self.assertEqual(deep["last_good"], 4)

    def test_tampered_checkpoint_anchor_falls_back_to_full_scan(self):
        self.fill(12)
        self.edit_record(9, action="HACK")
        log = self.open()
        shallow = log.verify()
        self.assertFalse(shallow["ok"])
        self.assertEqual(shallow["first_bad"], 10)
        self.assertEqual(shallow["checked"], 12)


class TestVerifyTails(ChainTestBase):
    def test_half_written_tail_is_the_last_consistent_point(self):
        self.fill(7)
        self.append_raw(b'{"seq":8,"act')
        log = self.open()
        self.assertEqual(log.count(), 7)
        result = log.verify()
        self.assertTrue(result["ok"])
        self.assertEqual(result["last_good"], 7)

    def test_append_after_torn_tail_continues_the_chain(self):
        self.fill(7)
        self.append_raw(b'{"seq":8,"act')
        log = self.open()
        record = log.append("act8", actor="u", detail="d", ts=8.0)
        self.assertEqual(record["seq"], 8)
        self.assertEqual(record[PREV_FIELD], log.read_all()[6]["digest"])
        self.assertEqual([r["seq"] for r in log.read_all()], list(range(1, 9)))
        self.assertTrue(log.verify(deep=True)["ok"])

    def test_truncated_tail_after_checkpoint_is_detected(self):
        self.fill(12)
        self.truncate_records(8)
        log = self.open()
        self.assertEqual(log.count(), 8)
        shallow = log.verify()
        deep = log.verify(deep=True)
        self.assertFalse(shallow["ok"])
        self.assertIsNone(shallow["first_bad"])
        self.assertEqual(shallow["last_good"], 8)
        self.assertEqual(shallow["checked"], 8)
        self.assertFalse(deep["ok"])
        self.assertEqual(deep["last_good"], 8)

    def test_truncation_down_to_nothing_reports_no_good_record(self):
        self.fill(12)
        self.truncate_records(0)
        log = self.open()
        result = log.verify(deep=True)
        self.assertFalse(result["ok"])
        self.assertIsNone(result["first_bad"])
        self.assertIsNone(result["last_good"])


class TestLegacyMigration(ChainTestBase):
    def test_legacy_log_opens_and_gets_chained_in_place(self):
        self.write_legacy(7)
        log = self.open()
        self.assertEqual(log.count(), 7)
        records = log.read_all()
        self.assertTrue(all(PREV_FIELD in record for record in records))
        self.assertEqual(records[0][PREV_FIELD], "")
        for index in range(1, 7):
            self.assertEqual(records[index][PREV_FIELD], records[index - 1]["digest"])
        self.assertTrue(log.verify(deep=True)["ok"])

    def test_legacy_content_is_preserved(self):
        self.write_legacy(3)
        log = self.open()
        records = log.read_all()
        self.assertEqual([r["action"] for r in records], ["old1", "old2", "old3"])
        self.assertEqual([r["seq"] for r in records], [1, 2, 3])

    def test_appends_continue_the_migrated_chain(self):
        self.write_legacy(7)
        log = self.open()
        added = log.append("new8", actor="u", detail="d", ts=8.0)
        records = log.read_all()
        self.assertEqual(added[PREV_FIELD], records[6]["digest"])
        self.assertTrue(log.verify(deep=True)["ok"])

    def test_reopening_migrated_log_does_not_migrate_again(self):
        self.write_legacy(7)
        self.open()
        size_after_migration = os.path.getsize(self.path)
        self.open()
        self.assertEqual(os.path.getsize(self.path), size_after_migration)


class TestConcurrentChain(ChainTestBase):
    def test_concurrent_appends_form_one_linear_chain(self):
        log = self.open(every=50)

        def worker(tag):
            for _ in range(100):
                log.append("job", actor=tag, detail="d", ts=1.0)

        threads = [threading.Thread(target=worker, args=("t%d" % i,)) for i in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(log.count(), 800)
        records = log.read_all()
        self.assertEqual([r["seq"] for r in records], list(range(1, 801)))
        for index in range(1, 800):
            self.assertEqual(records[index][PREV_FIELD], records[index - 1]["digest"])
        self.assertTrue(log.verify(deep=True)["ok"])


class TestPerformance(ChainTestBase):
    def test_100k_append_and_verify_under_one_minute(self):
        path = os.path.join(self.tmpdir, "big.log")
        log = AuditLog(path)
        started = time.perf_counter()
        for seq in range(1, 100001):
            log.append("login", actor="u%d" % seq, detail="d", ts=float(seq))
        appended = time.perf_counter()
        shallow = log.verify()
        shallow_done = time.perf_counter()
        deep = log.verify(deep=True)
        deep_done = time.perf_counter()

        self.assertTrue(shallow["ok"])
        self.assertTrue(deep["ok"])
        self.assertEqual(deep["checked"], 100000)
        self.assertLess(deep_done - started, 60.0)
        print(
            "\n100k: append %.1fs shallow %.2fs deep %.2fs"
            % (appended - started, shallow_done - appended, deep_done - shallow_done)
        )


if __name__ == "__main__":
    unittest.main()
