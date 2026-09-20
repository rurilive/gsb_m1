"""WAL 行为：崩溃恢复、快照对齐、日志裁剪、坏记录、并发顺序。"""
import json
import os
import shutil
import tempfile
import threading
import unittest
import zlib

from idxstore import WAL_NAME, IndexStore


def wal_line(record):
    body = json.dumps(record, sort_keys=True)
    crc = zlib.crc32(body.encode("utf-8"))
    return json.dumps(dict(record, crc=crc), sort_keys=True) + "\n"


class WalTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="idxstore-wal-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _wal_path(self):
        return os.path.join(self.dir, WAL_NAME)

    def _wal_records(self):
        with open(self._wal_path()) as f:
            return [json.loads(line) for line in f]


class TestCrashRecovery(WalTest):
    def test_changes_without_snapshot_survive_reopen(self):
        s = IndexStore(self.dir)
        s.put("d1", "alpha beta")
        s.put("d2", "beta gamma")
        s.delete("d1")
        # 模拟进程被 kill：不 snapshot，直接丢掉对象
        reopened = IndexStore(self.dir)
        self.assertEqual(reopened.load(), 1)
        self.assertEqual(reopened.search("beta"), ["d2"])
        self.assertIsNone(reopened.get("d1"))

    def test_reindex_through_wal(self):
        s = IndexStore(self.dir)
        s.put("d1", "alpha beta")
        s.put("d1", "beta gamma")
        reopened = IndexStore(self.dir)
        reopened.load()
        self.assertEqual(reopened.search("alpha"), [])
        self.assertEqual(reopened.search("gamma"), ["d1"])
        self.assertEqual(reopened.doc_count(), 1)

    def test_recovery_continues_after_reload(self):
        s = IndexStore(self.dir)
        s.put("d1", "alpha")
        reopened = IndexStore(self.dir)
        reopened.load()
        reopened.put("d2", "beta")
        again = IndexStore(self.dir)
        self.assertEqual(again.load(), 2)

    def test_seq_continues_when_writing_without_load(self):
        s = IndexStore(self.dir)
        s.put("d1", "alpha")
        s.snapshot()
        # 新进程没调 load 就直接写：seq 也必须接在快照之后
        s2 = IndexStore(self.dir)
        s2.put("d2", "beta")
        s2.close()
        reopened = IndexStore(self.dir)
        self.assertEqual(reopened.load(), 2)
        self.assertEqual(reopened.search("alpha"), ["d1"])
        self.assertEqual(reopened.search("beta"), ["d2"])


class TestSnapshotAlignment(WalTest):
    def test_delete_after_snapshot_does_not_resurrect(self):
        # 回滚事故的复现：快照后的删除，恢复时不能复活
        s = IndexStore(self.dir)
        s.put("d1", "doomed doc")
        s.put("d2", "keeper")
        s.snapshot()
        s.delete("d1")
        reopened = IndexStore(self.dir)
        reopened.load()
        self.assertIsNone(reopened.get("d1"))
        self.assertEqual(reopened.search("keeper"), ["d2"])

    def test_stale_records_before_snapshot_seq_are_skipped(self):
        s = IndexStore(self.dir)
        s.put("d1", "alpha")
        s.put("d2", "beta")
        s.snapshot()
        # 模拟接错位置的旧日志：seq 早于快照的记录混了回来
        with open(self._wal_path(), "w") as f:
            f.write(wal_line({"seq": 1, "op": "delete", "doc_id": "d1"}))
            f.write(wal_line({"seq": 3, "op": "put", "doc_id": "d3", "text": "gamma"}))
        reopened = IndexStore(self.dir)
        self.assertEqual(reopened.load(), 3)
        self.assertEqual(reopened.get("d1"), "alpha")
        self.assertEqual(reopened.search("gamma"), ["d3"])


class TestTrim(WalTest):
    def test_snapshot_trims_wal(self):
        s = IndexStore(self.dir)
        s.put("d1", "alpha")
        self.assertTrue(os.path.exists(self._wal_path()))
        s.snapshot()
        self.assertFalse(os.path.exists(self._wal_path()))

    def test_wal_recreated_by_next_change(self):
        s = IndexStore(self.dir)
        s.put("d1", "alpha")
        s.snapshot()
        s.put("d2", "beta")
        self.assertTrue(os.path.exists(self._wal_path()))
        reopened = IndexStore(self.dir)
        self.assertEqual(reopened.load(), 2)

    def test_auto_snapshot_bounds_replay(self):
        s = IndexStore(self.dir, snapshot_every=5)
        for i in range(7):
            s.put("d%d" % i, "term%d" % i)
        self.assertEqual(len(self._wal_records()), 2)
        reopened = IndexStore(self.dir)
        self.assertEqual(reopened.load(), 7)


class TestTornRecord(WalTest):
    def test_torn_tail_is_ignored(self):
        s = IndexStore(self.dir)
        s.put("d1", "alpha")
        s.put("d2", "beta")
        # 模拟掉电：最后一条只写了一半
        with open(self._wal_path(), "ab") as f:
            f.write(b'{"seq": 3, "op": "put", "doc_id": "d3", "te')
        reopened = IndexStore(self.dir)
        self.assertEqual(reopened.load(), 2)
        self.assertEqual(reopened.search("alpha"), ["d1"])

    def test_bad_crc_stops_replay_without_raising(self):
        s = IndexStore(self.dir)
        s.put("d1", "alpha")
        with open(self._wal_path(), "a") as f:
            f.write(json.dumps({"seq": 2, "op": "put", "doc_id": "d2",
                                "text": "beta", "crc": 0}) + "\n")
        reopened = IndexStore(self.dir)
        self.assertEqual(reopened.load(), 1)

    def test_torn_tail_truncated_so_appends_stay_readable(self):
        s = IndexStore(self.dir)
        s.put("d1", "alpha")
        with open(self._wal_path(), "ab") as f:
            f.write(b'{"seq": 2, "op": "pu')
        reopened = IndexStore(self.dir)
        reopened.load()
        reopened.put("d2", "beta")
        again = IndexStore(self.dir)
        self.assertEqual(again.load(), 2)
        self.assertEqual(again.search("beta"), ["d2"])


class TestConcurrency(WalTest):
    def test_concurrent_puts_wal_order_matches_and_all_recovered(self):
        s = IndexStore(self.dir, snapshot_every=10000)

        def worker(n):
            for i in range(50):
                s.put("t%d-d%02d" % (n, i), "term%d extra" % n)

        threads = [threading.Thread(target=worker, args=(n,)) for n in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(s.doc_count(), 200)
        seqs = [r["seq"] for r in self._wal_records()]
        self.assertEqual(seqs, list(range(1, 201)))

        reopened = IndexStore(self.dir)
        self.assertEqual(reopened.load(), 200)
        for n in range(4):
            self.assertEqual(reopened.search("term%d" % n), s.search("term%d" % n))


if __name__ == "__main__":
    unittest.main()
