"""MVCC 事务测试。

三个核心场景都用 threading.Event 给两个线程定节奏，消除时序偶然性：
写冲突（first-committer-wins）、快照隔离、gc 后活跃快照仍可读。
"""

import json
import os
import tempfile
import threading
import unittest

from mvstore import ConflictError, Store


class TestWriteConflict(unittest.TestCase):
    def test_first_committer_wins(self):
        s = Store()
        s.put("k", 1)

        errors = []
        a_read = {}
        b_read = {}
        a_begun = threading.Event()
        a_go = threading.Event()
        a_committed = threading.Event()
        b_go = threading.Event()
        b_start = threading.Event()
        b_begun = threading.Event()

        def worker_a():
            tx = s.begin()
            a_begun.set()
            a_go.wait(5)
            a_read["v"] = tx.get("k")
            tx.put("k", "A")
            tx.commit()
            a_committed.set()

        def worker_b():
            b_start.wait(5)
            tx = s.begin()
            b_begun.set()
            b_go.wait(5)
            b_read["v"] = tx.get("k")
            tx.put("k", "B")
            try:
                tx.commit()
            except ConflictError as exc:
                errors.append(exc)

        ta = threading.Thread(target=worker_a)
        tb = threading.Thread(target=worker_b)
        ta.start()
        tb.start()
        a_begun.wait(5)
        # 让 B 也先 begin，确认两事务快照都早于 A 的提交，再放行 A
        b_start.set()
        b_begun.wait(5)
        a_go.set()
        a_committed.wait(5)
        b_go.set()
        ta.join(5)
        tb.join(5)

        self.assertEqual(a_read["v"], 1)
        self.assertEqual(b_read["v"], 1)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], ConflictError)
        self.assertEqual(s.get("k"), "A")

    def test_conflicted_tx_is_void(self):
        s = Store()
        s.put("k", 1)
        b_put = threading.Event()
        b_commit = threading.Event()

        def worker_b():
            tx = s.begin()
            b_put.wait(5)
            tx.put("k", "B")
            b_commit.wait(5)
            try:
                tx.commit()
            except ConflictError:
                pass

        tb = threading.Thread(target=worker_b)
        tb.start()
        tx_a = s.begin()
        tx_a.put("k", "A")
        tx_a.commit()
        b_put.set()
        b_commit.set()
        tb.join(5)

        self.assertEqual(s.get("k"), "A")
        tx_c = s.begin()
        self.assertEqual(tx_c.get("k"), "A")


class TestSnapshotIsolation(unittest.TestCase):
    def test_snapshot_read_stable_across_other_commit(self):
        s = Store()
        s.put("k", "v0")

        a_seen = {}
        a_started = threading.Event()
        b_go = threading.Event()
        b_done = threading.Event()

        def worker_a():
            tx = s.begin()
            a_started.set()
            b_go.wait(5)
            a_seen["before"] = tx.get("k")
            b_done.wait(5)
            # B 已提交新值，A 仍读自己 begin 时刻的快照
            a_seen["after"] = tx.get("k")
            # 不碰 k，改别的 key 应顺利提交
            tx.put("other", "mine")
            a_seen["ver"] = tx.commit()

        def worker_b():
            b_go.wait(5)
            tx = s.begin()
            tx.put("k", "v1")
            tx.commit()
            b_done.set()

        ta = threading.Thread(target=worker_a)
        tb = threading.Thread(target=worker_b)
        ta.start()
        a_started.wait(5)
        tb.start()
        b_go.set()
        ta.join(5)
        tb.join(5)

        self.assertEqual(a_seen["before"], "v0")
        self.assertEqual(a_seen["after"], "v0")
        self.assertEqual(s.get("k"), "v1")
        self.assertEqual(s.get("other"), "mine")
        self.assertIsNotNone(a_seen["ver"])


class TestGc(unittest.TestCase):
    def test_gc_keeps_versions_active_snapshot_needs(self):
        s = Store()
        s.put("k", "v1")

        a_reads = {}
        a_started = threading.Event()
        b_go = threading.Event()
        b_done = threading.Event()
        a_check = threading.Event()
        a_done = threading.Event()

        def worker_a():
            # 长事务：在 v1 时刻开快照，横跨 B 的两次提交与 gc
            tx = s.begin()
            a_started.set()
            b_go.wait(5)
            b_done.wait(5)
            s.gc()
            a_reads["after_gc"] = tx.get("k")
            a_check.set()
            a_done.wait(5)
            tx.rollback()

        def worker_b():
            b_go.wait(5)
            s.put("k", "v2")
            s.put("k", "v3")
            b_done.set()
            a_check.wait(5)

        ta = threading.Thread(target=worker_a)
        tb = threading.Thread(target=worker_b)
        ta.start()
        a_started.wait(5)
        tb.start()
        b_go.set()
        a_check.wait(5)
        tb.join(5)

        # gc 后活跃快照仍读到 v1
        self.assertEqual(a_reads["after_gc"], "v1")
        versions = s._versions["k"]
        self.assertEqual([v for v, _ in versions], [1, 3])
        # 新事务读最新版
        self.assertEqual(s.begin().get("k"), "v3")

        a_done.set()
        ta.join(5)
        # 活跃事务结束后再 gc：每 key 只留最新版
        s.gc()
        self.assertEqual([v for v, _ in s._versions["k"]], [3])

    def test_gc_no_active_keeps_only_latest_and_drops_tombstone(self):
        s = Store()
        s.put("k", "old")
        s.put("k", "new")
        s.gc()
        self.assertEqual([v for v, _ in s._versions["k"]], [2])

        self.assertTrue(s.delete("k"))
        s.gc()
        # 最新版是删除标记且无快照需要，整个 key 清掉
        self.assertNotIn("k", s._versions)
        self.assertIsNone(s.get("k"))


class TestTransactionMisc(unittest.TestCase):
    def test_rollback_discards_buffer(self):
        s = Store()
        s.put("k", 1)
        tx = s.begin()
        tx.put("k", 2)
        tx.put("x", 9)
        tx.delete("k")
        self.assertIsNone(tx.get("k"))
        tx.rollback()
        self.assertEqual(s.get("k"), 1)
        self.assertIsNone(s.get("x"))

    def test_buffered_delete_then_put_within_tx(self):
        s = Store()
        s.put("k", 1)
        tx = s.begin()
        tx.delete("k")
        self.assertIsNone(tx.get("k"))
        tx.put("k", 2)
        self.assertEqual(tx.get("k"), 2)
        tx.commit()
        self.assertEqual(s.get("k"), 2)

    def test_version_advances_on_commit_and_delete_conflict(self):
        s = Store()
        s.put("k", 1)
        before = s._version
        tx = s.begin()
        self.assertEqual(tx.snapshot, before)
        # 别人删除了 k：删除也是一次提交，写 k 的事务必须冲突
        self.assertTrue(s.delete("k"))
        tx.put("k", 2)
        with self.assertRaises(ConflictError):
            tx.commit()
        self.assertIsNone(s.get("k"))

    def test_put_none_value_is_present(self):
        s = Store()
        s.put("k", None)
        self.assertIsNone(s.get("k"))
        self.assertTrue(s.delete("k"))
        self.assertFalse(s.delete("k"))

    def test_used_tx_raises(self):
        s = Store()
        tx = s.begin()
        tx.put("k", 1)
        tx.commit()
        with self.assertRaises(RuntimeError):
            tx.get("k")
        tx2 = s.begin()
        tx2.rollback()
        with self.assertRaises(RuntimeError):
            tx2.put("k", 1)

    def test_tx_commit_persists_and_replays(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "store.log")
            s = Store(path)
            s.put("a", 1)
            tx = s.begin()
            tx.put("b", {"x": True})
            tx.put("c", 3)
            tx.delete("a")
            tx.commit()
            with open(path, "r", encoding="utf-8") as f:
                lines = [json.loads(x) for x in f if x.strip()]
            ops = [(r["op"], r["key"], r["ver"]) for r in lines]
            self.assertEqual(ops[0], ("put", "a", 1))
            self.assertEqual(ops[1], ("put", "b", 2))
            self.assertEqual(ops[2], ("put", "c", 2))
            self.assertEqual(ops[3], ("del", "a", 2))

            s2 = Store(path)
            self.assertIsNone(s2.get("a"))
            self.assertEqual(s2.get("b"), {"x": True})
            self.assertEqual(s2.get("c"), 3)
            # 重放后 key 最后提交版本恢复，冲突检测仍生效
            tx1 = s2.begin()
            s2.put("b", "outside")
            tx1.put("b", "inside")
            with self.assertRaises(ConflictError):
                tx1.commit()

    def test_legacy_log_without_version_replays(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "old.log")
            with open(path, "w", encoding="utf-8") as f:
                f.write(json.dumps({"op": "put", "key": "a", "value": 1}) + "\n")
                f.write(json.dumps({"op": "put", "key": "a", "value": 2}) + "\n")
                f.write(json.dumps({"op": "del", "key": "a"}) + "\n")
            s = Store(path)
            self.assertIsNone(s.get("a"))
            self.assertEqual(s._version, 3)


if __name__ == "__main__":
    unittest.main()
