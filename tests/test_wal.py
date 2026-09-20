"""WAL 行为：先落日志再改内存、增量恢复、边界与并发保序。"""
import json
import os
import shutil
import tempfile
import threading
import unittest
import zlib

from idxstore import SNAPSHOT_NAME, WAL_NAME, IndexStore


class WalTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="idxstore-wal-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _store(self, **kw):
        return IndexStore(self.dir, **kw)

    def _reopen(self, **kw):
        store = self._store(**kw)
        count = store.load()
        return store, count

    def _wal_path(self):
        return os.path.join(self.dir, WAL_NAME)

    def _snapshot_path(self):
        return os.path.join(self.dir, SNAPSHOT_NAME)

    def _raw_records(self):
        with open(self._wal_path(), "rb") as f:
            return [line for line in f.read().splitlines()]


class TestIncrementalRecovery(WalTest):
    def test_changes_survive_without_snapshot(self):
        store = self._store(snapshot_every=1000)
        store.put("d1", "quick brown fox")
        store.put("d2", "lazy dog")
        store.delete("d1")
        store.close()
        self.assertFalse(os.path.exists(self._snapshot_path()))

        reopened, count = self._reopen(snapshot_every=1000)
        self.assertEqual(count, 1)
        self.assertEqual(reopened.get("d2"), "lazy dog")
        self.assertIsNone(reopened.get("d1"))
        self.assertEqual(reopened.search("fox"), [])
        self.assertEqual(reopened.search("dog"), ["d2"])
        reopened.close()

    def test_replay_after_snapshot_is_incremental(self):
        store = self._store(snapshot_every=1000)
        store.put("d1", "alpha beta")
        store.snapshot()
        store.put("d2", "beta gamma")
        store.delete("d1")
        store.close()

        reopened, count = self._reopen(snapshot_every=1000)
        self.assertEqual(count, 1)
        self.assertIsNone(reopened.get("d1"))
        self.assertEqual(reopened.search("alpha"), [])
        self.assertEqual(reopened.search("gamma"), ["d2"])
        self.assertEqual(reopened.search("beta"), ["d2"])
        reopened.close()

    def test_deleted_doc_must_not_resurrect(self):
        # 历史事故：回滚版本把日志接错了快照位置，早删掉的文档复活。
        store = self._store(snapshot_every=1000)
        store.put("d1", "ghost term")
        store.put("d2", "keep term")
        store.snapshot()
        store.put("d3", "new term")
        store.delete("d1")
        store.close()

        # 快照含 d1/d2，日志只有 d3 与删除 d1。
        reopened, _ = self._reopen(snapshot_every=1000)
        self.assertEqual(reopened.doc_count(), 2)
        self.assertIsNone(reopened.get("d1"))
        self.assertEqual(reopened.search("ghost"), [])
        self.assertEqual(reopened.search("new"), ["d3"])
        reopened.close()

    def test_replayed_delete_of_missing_doc_is_noop(self):
        # 日志覆盖快照已有状态时，delete 必须保持幂等。
        store = self._store(snapshot_every=1000)
        store.put("d1", "a")
        store.put("d2", "b")
        store.snapshot()
        store.delete("d1")
        store.close()
        with open(self._snapshot_path()) as f:
            snapshot_before = f.read()

        reopened1, _ = self._reopen(snapshot_every=1000)
        reopened1.close()
        reopened2, count = self._reopen(snapshot_every=1000)
        self.assertEqual(count, 1)
        self.assertEqual(reopened2.search("a"), [])
        self.assertEqual(reopened2.search("b"), ["d2"])
        # 重放本身不重写快照。
        with open(self._snapshot_path()) as f:
            self.assertEqual(f.read(), snapshot_before)
        reopened2.close()

    def test_recovery_after_auto_snapshot_keeps_tail_changes(self):
        store = self._store(snapshot_every=2)
        store.put("d1", "a")
        store.put("d2", "b")  # 触发自动快照并裁剪日志
        store.put("d3", "c")
        store.close()

        reopened, count = self._reopen(snapshot_every=1000)
        self.assertEqual(count, 3)
        self.assertEqual(reopened.search("c"), ["d3"])
        reopened.close()


class TestWALTrimming(WalTest):
    def test_wal_removed_when_snapshot_is_taken(self):
        store = self._store()
        store.put("d1", "alpha")
        self.assertTrue(os.path.exists(self._wal_path()))
        store.snapshot()
        self.assertFalse(os.path.exists(self._wal_path()))
        store.close()

    def test_writes_after_trim_start_fresh_log(self):
        store = self._store()
        store.put("d1", "alpha")
        store.snapshot()
        store.put("d2", "beta")
        store.close()

        records = self._raw_records()
        self.assertEqual(len(records), 1)
        reopened, _ = self._reopen(snapshot_every=1000)
        self.assertEqual(reopened.get("d1"), "alpha")
        self.assertEqual(reopened.get("d2"), "beta")
        reopened.close()


class TestTornAndCorruptRecords(WalTest):
    def _append_torn_tail(self):
        store = self._store(snapshot_every=1000)
        store.put("d1", "good one")
        store.close()
        payload = json.dumps(["put", "d2", "half written"]).encode("utf-8")
        head = b"%d:%08x:" % (len(payload), zlib.crc32(payload) & 0xFFFFFFFF)
        with open(self._wal_path(), "ab") as f:
            f.write(head + payload[:7])  # 只有半截 payload，没有换行

    def test_half_written_last_record_is_dropped_not_raised(self):
        self._append_torn_tail()
        reopened, count = self._reopen(snapshot_every=1000)
        self.assertEqual(count, 1)
        self.assertEqual(reopened.get("d1"), "good one")
        self.assertIsNone(reopened.get("d2"))

        # 坏尾巴已被截断，之后追加的记录不受影响。
        reopened.put("d3", "good three")
        reopened.close()
        again, count = self._reopen(snapshot_every=1000)
        self.assertEqual(count, 2)
        self.assertEqual(again.get("d3"), "good three")
        again.close()

    def test_bad_checksum_is_treated_as_corrupt(self):
        store = self._store(snapshot_every=1000)
        store.put("d1", "good")
        store.close()
        with open(self._wal_path(), "ab") as f:
            f.write(b"20:deadbeef:[\"put\",\"d2\",\"x\"]\n")

        reopened, count = self._reopen(snapshot_every=1000)
        self.assertEqual(count, 1)
        self.assertIsNone(reopened.get("d2"))
        # 截断点恰好在坏记录之前，新记录从此处追加、再次恢复依然正确。
        reopened.put("d4", "after cut")
        reopened.close()
        again, count = self._reopen(snapshot_every=1000)
        self.assertEqual(count, 2)
        self.assertEqual(again.get("d4"), "after cut")
        again.close()

    def test_replay_stops_at_first_bad_record(self):
        store = self._store(snapshot_every=1000)
        store.put("d1", "good")
        store.close()
        with open(self._wal_path(), "ab") as f:
            f.write(b"garbage-not-a-record\n")
            payload = json.dumps(["put", "d9", "unreachable"]).encode("utf-8")
            head = b"%d:%08x:" % (len(payload), zlib.crc32(payload) & 0xFFFFFFFF)
            f.write(head + payload + b"\n")

        reopened, count = self._reopen(snapshot_every=1000)
        self.assertEqual(count, 1)
        self.assertIsNone(reopened.get("d9"))
        reopened.close()

    def test_empty_wal_is_harmless(self):
        open(self._wal_path(), "wb").close()
        reopened, count = self._reopen()
        self.assertEqual(count, 0)
        reopened.put("d1", "fresh")
        reopened.close()

    def test_half_written_snapshot_tempfile_is_cleaned_up(self):
        store = self._store()
        store.put("d1", "alpha")
        store.close()
        tmp = os.path.join(self.dir, ".%s.tmpXXXX" % SNAPSHOT_NAME)
        with open(tmp, "wb") as f:
            f.write(b"{half")

        reopened, count = self._reopen(snapshot_every=1000)
        self.assertEqual(count, 1)
        self.assertFalse(
            any(name.startswith(".%s.tmp" % SNAPSHOT_NAME)
                for name in os.listdir(self.dir)))
        reopened.close()


class TestOrdering(WalTest):
    def test_concurrent_writes_replay_in_effective_order(self):
        store = self._store(snapshot_every=1000)
        errors = []

        def worker(start):
            try:
                for i in range(start, start + 50):
                    doc_id = "d%03d" % i
                    store.put(doc_id, "word %d" % i)
                    if i % 3 == 0:
                        store.put(doc_id, "reword %d" % i)
            except Exception as exc:  # pragma: no cover - 测试失败时留痕
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(t * 100,))
                   for t in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        store.close()

        # 日志里每个 doc 的最终一条记录必须与内存最终状态一致。
        records = [
            json.loads(line.split(b":", 2)[2].decode("utf-8"))
            for line in self._raw_records()
        ]
        final_by_log = {}
        for op, doc_id, text in records:
            if op == "put":
                final_by_log[doc_id] = text
            else:
                final_by_log.pop(doc_id, None)

        reopened, count = self._reopen(snapshot_every=1000)
        self.assertEqual(count, 200)
        for doc_id, text in final_by_log.items():
            self.assertEqual(reopened.get(doc_id), text, doc_id)
        reopened.close()


if __name__ == "__main__":
    unittest.main()
