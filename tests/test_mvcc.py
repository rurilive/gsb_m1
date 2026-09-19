"""MVCC 事务语义测试：写冲突、快照隔离、gc 与活跃快照。"""

import threading
import unittest

from mvstore.store import ConflictError, Store


class TestMVCC(unittest.TestCase):
    def test_write_conflict_first_committer_wins(self):
        s = Store()
        s.put("k", 0)
        began = {"a": threading.Event(), "b": threading.Event()}
        go = {"a": threading.Event(), "b": threading.Event()}
        done = {"a": threading.Event(), "b": threading.Event()}
        results = {}

        def worker(name, value):
            tx = s.begin()
            began[name].set()
            go[name].wait()
            tx.put("k", value)
            try:
                tx.commit()
                results[name] = "ok"
            except ConflictError:
                results[name] = "conflict"
            done[name].set()

        ta = threading.Thread(target=worker, args=("a", 1))
        tb = threading.Thread(target=worker, args=("b", 2))
        ta.start()
        tb.start()
        began["a"].wait()
        began["b"].wait()
        go["a"].set()
        done["a"].wait()  # a 先提交成功
        go["b"].set()
        done["b"].wait()
        ta.join()
        tb.join()

        self.assertEqual(results["a"], "ok")
        self.assertEqual(results["b"], "conflict")
        self.assertEqual(s.get("k"), 1)

    def test_snapshot_isolation(self):
        s = Store()
        s.put("k", "v0")
        began = threading.Event()
        committed = threading.Event()
        seen = {}

        def reader():
            tx = s.begin()
            began.set()
            committed.wait()  # 等另一个事务提交后再读
            seen["v"] = tx.get("k")
            tx.rollback()

        t = threading.Thread(target=reader)
        t.start()
        began.wait()
        w = s.begin()
        w.put("k", "v1")
        w.commit()
        committed.set()
        t.join()

        self.assertEqual(seen["v"], "v0")  # 读 begin 时刻快照
        self.assertEqual(s.get("k"), "v1")

    def test_gc_keeps_version_for_active_snapshot(self):
        s = Store()
        s.put("k", "v0")
        began = threading.Event()
        release = threading.Event()
        seen = {}

        def reader():
            tx = s.begin()
            began.set()
            release.wait()  # 等主线程写新版本并 gc 后再读
            seen["v"] = tx.get("k")
            tx.rollback()

        t = threading.Thread(target=reader)
        t.start()
        began.wait()
        s.put("k", "v1")
        s.put("k", "v2")
        s.gc()
        self.assertGreater(len(s._versions["k"]), 1)  # 活跃快照引用的旧版本保留
        release.set()
        t.join()

        self.assertEqual(seen["v"], "v0")  # gc 后活跃快照仍读到旧值
        s.gc()
        self.assertEqual(len(s._versions["k"]), 1)  # 无活跃事务只留最新版
        self.assertEqual(s.get("k"), "v2")

    def test_rollback_discards_buffer(self):
        s = Store()
        s.put("k", 1)
        tx = s.begin()
        tx.put("k", 2)
        self.assertEqual(tx.get("k"), 2)  # 写缓冲对自己可见
        tx.rollback()
        self.assertEqual(s.get("k"), 1)

    def test_commit_conflict_invalidates_transaction(self):
        s = Store()
        s.put("k", 0)
        t1 = s.begin()
        t2 = s.begin()
        t1.put("k", 1)
        t1.commit()
        t2.put("k", 2)
        with self.assertRaises(ConflictError):
            t2.commit()
        with self.assertRaises(RuntimeError):
            t2.get("k")  # 冲突后事务作废
        self.assertEqual(s.get("k"), 1)


if __name__ == "__main__":
    unittest.main()
