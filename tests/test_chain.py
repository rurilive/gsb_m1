"""防篡改链、检查点、补链迁移的新行为测试。"""

import json
import os
import shutil
import tempfile
import threading
import time
import unittest

from auditchain import AuditLog
from auditchain.codec import GENESIS_DIGEST, PREV_DIGEST_FIELD, record_digest
from auditchain.store import RecordStore


class ChainTestBase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="auditchain-chain-")
        self.path = os.path.join(self.tmpdir, "audit.log")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def write_raw(self, blob):
        with open(self.path, "ab") as handle:
            handle.write(blob)

    def read_lines(self):
        with open(self.path, "rb") as handle:
            return handle.readlines()

    def write_lines(self, lines):
        with open(self.path, "wb") as handle:
            handle.writelines(lines)

    def tamper_line(self, index_zero_based, mutate):
        """改掉磁盘上某一行的内容（不动摘要，模拟手改处罚记录）。"""
        lines = self.read_lines()
        record = json.loads(lines[index_zero_based])
        mutate(record)
        lines[index_zero_based] = json.dumps(
            record, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii") + b"\n"
        self.write_lines(lines)


class TestHashChain(ChainTestBase):
    def test_each_record_links_to_the_previous_digest(self):
        log = AuditLog(self.path, checkpoint_every=0)
        first = log.append("login", ts=1)
        second = log.append("export", ts=2)
        third = log.append("punish", ts=3)
        self.assertEqual(first[PREV_DIGEST_FIELD], GENESIS_DIGEST)
        self.assertEqual(second[PREV_DIGEST_FIELD], first["digest"])
        self.assertEqual(third[PREV_DIGEST_FIELD], second["digest"])

    def test_link_field_is_part_of_the_digest(self):
        log = AuditLog(self.path, checkpoint_every=0)
        record = log.append("login", ts=1)
        self.assertEqual(record["digest"], record_digest(record))

    def test_verify_result_keys_on_a_good_chain(self):
        log = AuditLog(self.path, checkpoint_every=0)
        for index in range(1, 6):
            log.append("act%d" % index, ts=index)
        self.assertEqual(
            log.verify(),
            {"ok": True, "first_bad": None, "last_good": 5, "checked": 5},
        )

    def test_empty_log_verifies_ok(self):
        log = AuditLog(self.path)
        self.assertEqual(
            log.verify(),
            {"ok": True, "first_bad": None, "last_good": 0, "checked": 0},
        )
        self.assertFalse(os.path.exists(self.path))


class TestTamperDetection(ChainTestBase):
    def test_modifying_a_record_is_reported_with_its_number_deep(self):
        log = AuditLog(self.path, checkpoint_every=0)
        for index in range(1, 11):
            log.append("punish", actor="wang", detail="记录%d" % index, ts=index)
        self.tamper_line(6, lambda record: record.update(detail="洗白"))
        reopened = AuditLog(self.path, checkpoint_every=0)
        result = reopened.verify(deep=True)
        self.assertFalse(result["ok"])
        self.assertEqual(result["first_bad"], 7)
        self.assertEqual(result["last_good"], 6)
        self.assertEqual(result["checked"], 7)

    def test_modifying_the_first_record_is_reported(self):
        log = AuditLog(self.path, checkpoint_every=0)
        for index in range(1, 4):
            log.append("act%d" % index, ts=index)
        self.tamper_line(0, lambda record: record.update(action="x"))
        reopened = AuditLog(self.path, checkpoint_every=0)
        result = reopened.verify(deep=True)
        self.assertEqual(result["first_bad"], 1)
        self.assertEqual(result["last_good"], 0)

    def test_retargeting_a_link_without_touching_content_breaks_the_chain(self):
        log = AuditLog(self.path, checkpoint_every=0)
        for index in range(1, 5):
            log.append("act%d" % index, ts=index)
        self.tamper_line(2, lambda record: record.update(prev_digest="deadbeef"))
        reopened = AuditLog(self.path, checkpoint_every=0)
        result = reopened.verify(deep=True)
        self.assertEqual(result["first_bad"], 3)
        self.assertEqual(result["last_good"], 2)

    def test_deleting_a_middle_record_gaps_the_sequence(self):
        log = AuditLog(self.path, checkpoint_every=0)
        for index in range(1, 6):
            log.append("act%d" % index, ts=index)
        lines = self.read_lines()
        del lines[2]
        self.write_lines(lines)
        reopened = AuditLog(self.path, checkpoint_every=0)
        result = reopened.verify(deep=True)
        self.assertEqual(result["first_bad"], 3)
        self.assertEqual(result["last_good"], 2)


class TestCheckpoints(ChainTestBase):
    def test_checkpoint_is_written_every_n_records(self):
        log = AuditLog(self.path, checkpoint_every=3)
        for index in range(1, 8):
            log.append("act%d" % index, ts=index)
        self.assertTrue(os.path.exists(log.checkpoint_path))
        with open(log.checkpoint_path, "rb") as handle:
            checkpoints = [json.loads(line) for line in handle.read().splitlines()]
        self.assertEqual([entry["seq"] for entry in checkpoints], [3, 6])

    def test_incremental_verify_starts_at_the_latest_checkpoint(self):
        log = AuditLog(self.path, checkpoint_every=5)
        for index in range(1, 13):
            log.append("act%d" % index, ts=index)
        result = log.verify()
        self.assertTrue(result["ok"])
        self.assertEqual(result["last_good"], 12)
        # 锚点第 10 条含在本次核对里，到第 12 条一共算 3 条。
        self.assertEqual(result["checked"], 3)

    def test_deep_verify_checks_every_single_record(self):
        log = AuditLog(self.path, checkpoint_every=5)
        for index in range(1, 13):
            log.append("act%d" % index, ts=index)
        result = log.verify(deep=True)
        self.assertTrue(result["ok"])
        self.assertEqual(result["checked"], 12)
        self.assertIsNone(result["first_bad"])

    def test_tamper_before_checkpoint_hidden_incrementally_but_found_deep(self):
        log = AuditLog(self.path, checkpoint_every=5)
        for index in range(1, 13):
            log.append("punish", detail="v%d" % index, ts=index)
        self.tamper_line(2, lambda record: record.update(detail="改写"))
        reopened = AuditLog(self.path, checkpoint_every=5)
        self.assertTrue(reopened.verify()["ok"])
        result = reopened.verify(deep=True)
        self.assertFalse(result["ok"])
        self.assertEqual(result["first_bad"], 3)
        self.assertEqual(result["last_good"], 2)

    def test_tamper_after_the_checkpoint_is_found_incrementally(self):
        log = AuditLog(self.path, checkpoint_every=5)
        for index in range(1, 13):
            log.append("punish", detail="v%d" % index, ts=index)
        self.tamper_line(9, lambda record: record.update(detail="改写"))
        reopened = AuditLog(self.path, checkpoint_every=5)
        result = reopened.verify()
        self.assertFalse(result["ok"])
        self.assertEqual(result["first_bad"], 10)
        self.assertEqual(result["last_good"], 9)

    def test_tail_truncation_past_checkpoint_is_reported(self):
        log = AuditLog(self.path, checkpoint_every=5)
        for index in range(1, 13):
            log.append("act%d" % index, ts=index)
        self.write_lines(self.read_lines()[:8])
        reopened = AuditLog(self.path, checkpoint_every=5)
        result = reopened.verify()
        self.assertFalse(result["ok"])
        self.assertEqual(result["first_bad"], 9)
        self.assertEqual(result["last_good"], 8)
        self.assertEqual(reopened.verify(deep=True)["first_bad"], 9)

    def test_forged_checkpoint_with_bad_signature_is_ignored(self):
        log = AuditLog(self.path, checkpoint_every=5)
        for index in range(1, 13):
            log.append("act%d" % index, ts=index)
        with open(log.checkpoint_path, "rb") as handle:
            last = json.loads(handle.read().strip().split(b"\n")[-1])
        last["seq"] = 999
        with open(log.checkpoint_path, "ab") as handle:
            handle.write(
                json.dumps(last, separators=(",", ":")).encode("ascii") + b"\n"
            )
        result = log.verify()
        self.assertTrue(result["ok"])
        self.assertEqual(result["last_good"], 12)

    def test_torn_checkpoint_line_is_skipped(self):
        log = AuditLog(self.path, checkpoint_every=5)
        for index in range(1, 7):
            log.append("act%d" % index, ts=index)
        with open(log.checkpoint_path, "ab") as handle:
            handle.write(b'{"seq": 10, "dig')
        result = log.verify()
        self.assertTrue(result["ok"])
        self.assertEqual(result["checked"], 2)


class TestTornTail(ChainTestBase):
    def test_half_written_tail_is_not_a_bad_chain(self):
        log = AuditLog(self.path, checkpoint_every=0)
        for index in range(1, 4):
            log.append("act%d" % index, ts=index)
        self.write_raw(b'{"seq":4,"act')
        reopened = AuditLog(self.path, checkpoint_every=0)
        result = reopened.verify()
        self.assertTrue(result["ok"])
        self.assertEqual(result["last_good"], 3)
        self.assertIsNone(result["first_bad"])

    def test_torn_tail_is_healed_and_appending_continues_the_chain(self):
        log = AuditLog(self.path, checkpoint_every=0)
        for index in range(1, 4):
            log.append("act%d" % index, ts=index)
        self.write_raw(b'{"seq":4,"act')
        reopened = AuditLog(self.path, checkpoint_every=0)
        record = reopened.append("act4", ts=4)
        self.assertEqual(record["seq"], 4)
        self.assertEqual(reopened.count(), 4)
        self.assertTrue(reopened.verify(deep=True)["ok"])
        actions = [record["action"] for record in reopened.read_all()]
        self.assertEqual(actions, ["act1", "act2", "act3", "act4"])


class TestLegacyMigration(ChainTestBase):
    def _write_legacy(self, count):
        store = RecordStore(self.path)
        for index in range(1, count + 1):
            record = {
                "seq": index,
                "ts": float(index),
                "action": "old%d" % index,
                "actor": "",
                "detail": "",
            }
            record["digest"] = record_digest(record)
            store.append(record)

    def test_legacy_log_is_backfilled_in_place_not_rejected(self):
        self._write_legacy(7)
        log = AuditLog(self.path, checkpoint_every=0)
        self.assertEqual(log.count(), 7)
        records = log.read_all()
        self.assertTrue(all(PREV_DIGEST_FIELD in record for record in records))
        self.assertTrue(log.verify(deep=True)["ok"])

    def test_backfill_recomputes_digests_and_links(self):
        self._write_legacy(3)
        log = AuditLog(self.path, checkpoint_every=0)
        records = log.read_all()
        self.assertEqual(records[0][PREV_DIGEST_FIELD], GENESIS_DIGEST)
        self.assertEqual(records[1][PREV_DIGEST_FIELD], records[0]["digest"])
        self.assertEqual(records[2][PREV_DIGEST_FIELD], records[1]["digest"])
        for record in records:
            self.assertEqual(record["digest"], record_digest(record))

    def test_backfilled_log_accepts_new_chained_records(self):
        self._write_legacy(3)
        log = AuditLog(self.path, checkpoint_every=0, clock=lambda: 99.0)
        appended = log.append("new", ts=99)
        self.assertEqual(appended["seq"], 4)
        self.assertEqual(appended[PREV_DIGEST_FIELD], log.read_all()[2]["digest"])
        self.assertTrue(log.verify(deep=True)["ok"])

    def test_legacy_torn_tail_is_healed_then_backfilled(self):
        self._write_legacy(3)
        self.write_raw(b'{"seq":4,')
        log = AuditLog(self.path, checkpoint_every=0)
        self.assertEqual(log.count(), 3)
        self.assertTrue(log.verify(deep=True)["ok"])

    def test_mixed_chain_is_not_silently_rechained(self):
        log = AuditLog(self.path, checkpoint_every=0)
        for index in range(1, 5):
            log.append("act%d" % index, ts=index)
        self.tamper_line(2, lambda record: record.pop(PREV_DIGEST_FIELD))
        reopened = AuditLog(self.path, checkpoint_every=0)
        result = reopened.verify(deep=True)
        self.assertFalse(result["ok"])
        self.assertEqual(result["first_bad"], 3)


class TestConcurrentChain(ChainTestBase):
    def test_concurrent_appends_keep_one_linear_chain(self):
        log = AuditLog(self.path, checkpoint_every=100)

        def worker(tag):
            for _ in range(100):
                log.append("job", actor=tag, ts=1)

        threads = [
            threading.Thread(target=worker, args=("t%d" % index,))
            for index in range(8)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(log.count(), 800)
        records = log.read_all()
        self.assertEqual([record["seq"] for record in records], list(range(1, 801)))
        for index, record in enumerate(records):
            if index == 0:
                self.assertEqual(record[PREV_DIGEST_FIELD], GENESIS_DIGEST)
            else:
                self.assertEqual(
                    record[PREV_DIGEST_FIELD], records[index - 1]["digest"]
                )
        self.assertTrue(log.verify(deep=True)["ok"])


class TestScale(ChainTestBase):
    def test_one_hundred_thousand_appends_and_verify_under_one_minute(self):
        log = AuditLog(self.path, checkpoint_every=1000)
        start = time.perf_counter()
        for index in range(1, 100001):
            log.append("punish", detail="记录%d" % index, ts=index)
        append_seconds = time.perf_counter() - start

        start = time.perf_counter()
        result = log.verify(deep=True)
        deep_seconds = time.perf_counter() - start

        start = time.perf_counter()
        incremental = log.verify()
        incremental_seconds = time.perf_counter() - start

        self.assertEqual(log.count(), 100000)
        self.assertTrue(result["ok"])
        self.assertEqual(result["checked"], 100000)
        self.assertTrue(incremental["ok"])
        self.assertLess(append_seconds + deep_seconds, 60.0)
        self.assertLess(incremental_seconds, 10.0)
