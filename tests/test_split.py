"""在线分裂的行为测试。

覆盖：只劈目标片（别片一个键不动）、搬迁期读写语义（读回捞、写双落）、
进度可见、断点续搬、提交原子可回退、连续分裂路由不退化。
"""
import os
import tempfile
import threading
import unittest

from shardstore import ShardedKV

BASE = ["s0", "s1", "s2"]


def populate(kv, n=300, prefix="k"):
    keys = ["%s:%d" % (prefix, i) for i in range(n)]
    for i, key in enumerate(keys):
        kv.put(key, i)
    return keys


def fullest(kv):
    dist = kv.distribution()
    return max(dist, key=dist.get)


class SplitTestBase(unittest.TestCase):
    def setUp(self):
        self.kv = ShardedKV(BASE)
        self.keys = populate(self.kv)
        self.parent = fullest(self.kv)
        self.child = self.parent + "-b"
        self.before = {k: self.kv.shard_of(k) for k in self.keys}


class TestSplitRouting(SplitTestBase):
    def test_only_parent_keys_move_and_half_split(self):
        self.kv.begin_split(self.parent, self.child)
        self.kv.migrate_all()
        self.kv.commit_split()
        moved = [k for k in self.keys if self.kv.shard_of(k) == self.child]
        stayed = [k for k in self.keys if self.kv.shard_of(k) == self.parent]
        self.assertTrue(moved)
        self.assertTrue(stayed)
        for key in self.keys:
            if self.before[key] != self.parent:
                # 别片一个键不动
                self.assertEqual(self.kv.shard_of(key), self.before[key])
            else:
                self.assertIn(self.kv.shard_of(key), (self.parent, self.child))
        self.assertEqual(self.kv.size(self.child), len(moved))
        self.assertEqual(self.kv.total(), len(self.keys))
        ratio = len(moved) / float(len(moved) + len(stayed))
        self.assertTrue(0.3 < ratio < 0.7)

    def test_route_pinned_to_parent_until_commit(self):
        self.kv.begin_split(self.parent, self.child)
        self.kv.migrate_some(10)
        for key in self.keys:
            self.assertEqual(self.kv.shard_of(key), self.before[key])

    def test_partition_invariant_after_commit(self):
        self.kv.begin_split(self.parent, self.child)
        self.kv.migrate_all()
        self.kv.commit_split()
        for shard in self.kv.shards():
            for key in self.kv.keys_in(shard):
                self.assertEqual(self.kv.shard_of(key), shard)
        self.assertEqual(self.kv.total(), len(self.keys))

    def test_repeated_splits_do_not_reshuffle(self):
        self.kv.begin_split(self.parent, self.child)
        self.kv.migrate_all()
        self.kv.commit_split()
        mid = {k: self.kv.shard_of(k) for k in self.keys}
        second = fullest(self.kv)
        self.kv.begin_split(second, second + "-c")
        self.kv.migrate_all()
        self.kv.commit_split()
        self.assertEqual(len(self.kv), 5)
        for key in self.keys:
            if mid[key] != second:
                # 第二次分裂也不碰别的片
                self.assertEqual(self.kv.shard_of(key), mid[key])
            self.assertEqual(self.kv.shard_of(key), self.kv.shard_of(key))
        for shard in self.kv.shards():
            for key in self.kv.keys_in(shard):
                self.assertEqual(self.kv.shard_of(key), shard)
        self.assertEqual(self.kv.total(), len(self.keys))


class TestMigrationReadWrite(SplitTestBase):
    def test_reads_succeed_throughout_migration(self):
        self.kv.begin_split(self.parent, self.child)
        self.kv.migrate_some(7)
        for i, key in enumerate(self.keys):
            self.assertEqual(self.kv.get(key), i)
        self.kv.migrate_all()
        for i, key in enumerate(self.keys):
            self.assertEqual(self.kv.get(key), i)
        self.kv.commit_split()
        for i, key in enumerate(self.keys):
            self.assertEqual(self.kv.get(key), i)

    def test_put_dual_writes_migrated_key(self):
        self.kv.begin_split(self.parent, self.child)
        self.assertEqual(self.kv.migrate_some(1), 1)
        hot = self.kv.keys_in(self.child)[0]
        self.assertEqual(self.kv.put(hot, "v2"), self.parent)
        self.assertEqual(self.kv.get(hot), "v2")
        self.kv.migrate_all()
        self.kv.commit_split()
        self.assertEqual(self.kv.shard_of(hot), self.child)
        self.assertEqual(self.kv.get(hot), "v2")
        self.assertNotIn(hot, self.kv.keys_in(self.parent))

    def test_put_during_migration_survives_commit(self):
        self.kv.begin_split(self.parent, self.child)
        for key in self.keys:
            if self.kv.shard_of(key) == self.parent:
                self.kv.put(key, "new:" + key)
        self.kv.migrate_all()
        self.kv.commit_split()
        for key in self.keys:
            if self.before[key] == self.parent:
                self.assertEqual(self.kv.get(key), "new:" + key)
            else:
                self.assertEqual(self.kv.get(key), self.keys.index(key))

    def test_delete_during_migration_hits_both_sides(self):
        self.kv.begin_split(self.parent, self.child)
        self.kv.migrate_some(1)
        migrated = self.kv.keys_in(self.child)[0]
        self.assertTrue(self.kv.delete(migrated))
        self.assertIsNone(self.kv.get(migrated))
        victim = next(k for k in self.keys
                      if self.kv.shard_of(k) == self.parent and k != migrated)
        self.assertTrue(self.kv.delete(victim))
        self.kv.migrate_all()
        self.kv.commit_split()
        self.assertIsNone(self.kv.get(migrated))
        self.assertIsNone(self.kv.get(victim))
        self.assertEqual(self.kv.total(), len(self.keys) - 2)


class TestProgress(SplitTestBase):
    def test_no_split_reports_none(self):
        self.assertIsNone(self.kv.split_progress())
        self.assertIsNone(self.kv.splitting())

    def test_progress_counts_down_to_zero(self):
        self.kv.begin_split(self.parent, self.child)
        self.assertEqual(self.kv.splitting(), (self.parent, self.child))
        prog = self.kv.split_progress()
        self.assertEqual(prog["moved"], 0)
        self.assertEqual(prog["total"], prog["remaining"])
        self.assertTrue(0 < prog["total"] <= self.kv.size(self.parent))
        total = prog["total"]
        seen = 0
        while True:
            moved = self.kv.migrate_some(3)
            if moved == 0:
                break
            seen += moved
            prog = self.kv.split_progress()
            self.assertEqual(prog["moved"], seen)
            self.assertEqual(prog["remaining"], total - seen)
            self.assertEqual(prog["total"], total)
        self.assertEqual(seen, total)
        self.assertEqual(self.kv.split_progress()["remaining"], 0)


class TestValidation(SplitTestBase):
    def test_begin_rejects_unknown_parent(self):
        with self.assertRaises(KeyError):
            self.kv.begin_split("nope", "x")

    def test_begin_rejects_bad_child_id(self):
        with self.assertRaises(ValueError):
            self.kv.begin_split(self.parent, "")
        with self.assertRaises(ValueError):
            self.kv.begin_split(self.parent, self.parent)

    def test_only_one_split_at_a_time(self):
        self.kv.begin_split(self.parent, self.child)
        with self.assertRaises(RuntimeError):
            self.kv.begin_split("s0", "other-child")

    def test_commit_requires_full_migration(self):
        self.kv.begin_split(self.parent, self.child)
        self.kv.migrate_some(1)
        with self.assertRaises(RuntimeError):
            self.kv.commit_split()

    def test_migration_calls_require_active_split(self):
        with self.assertRaises(RuntimeError):
            self.kv.migrate_some(1)
        with self.assertRaises(RuntimeError):
            self.kv.commit_split()
        with self.assertRaises(RuntimeError):
            self.kv.abort_split()


class TestRestartResume(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "split.state")

    def _open(self):
        return ShardedKV(BASE, state_path=self.path)

    def test_resume_from_checkpoint_after_restart(self):
        kv1 = self._open()
        keys = populate(kv1)
        parent = fullest(kv1)
        child = parent + "-b"
        kv1.begin_split(parent, child)
        kv1.migrate_some(5)
        self.assertEqual(kv1.split_progress()["moved"], 5)
        journaled = {k: kv1.get(k) for k in kv1.keys_in(child)}
        self.assertEqual(len(journaled), 5)

        # 进程重启：同一 state_path 开新实例
        kv2 = self._open()
        self.assertIn(child, kv2.shards())
        prog = kv2.split_progress()
        self.assertEqual(prog["moved"], 5)  # 断点还在，不从头搬
        for key, value in journaled.items():
            self.assertEqual(kv2.get(key), value)  # 已搬的键从日志恢复
            self.assertEqual(kv2.shard_of(key), parent)  # 路由没有提前切

        # 缓存回源：老片数据重新灌入，已搬的键不重搬
        for i, key in enumerate(keys):
            kv2.put(key, i)
        self.assertEqual(kv2.split_progress()["moved"], 5)
        kv2.migrate_all()
        kv2.commit_split()
        for i, key in enumerate(keys):
            self.assertEqual(kv2.get(key), i)
        for shard in kv2.shards():
            for key in kv2.keys_in(shard):
                self.assertEqual(kv2.shard_of(key), shard)
        self.assertEqual(kv2.total(), len(keys))

    def test_committed_routing_recovers(self):
        kv1 = self._open()
        keys = populate(kv1)
        parent = fullest(kv1)
        kv1.begin_split(parent, parent + "-b")
        kv1.migrate_all()
        kv1.commit_split()
        routed = {k: kv1.shard_of(k) for k in keys}

        kv2 = self._open()
        self.assertIsNone(kv2.split_progress())
        self.assertIn(parent + "-b", kv2.shards())
        for key in keys:
            self.assertEqual(kv2.shard_of(key), routed[key])

    def test_abort_rolls_back_everything(self):
        kv1 = self._open()
        keys = populate(kv1)
        parent = fullest(kv1)
        child = parent + "-b"
        before = {k: kv1.shard_of(k) for k in keys}
        kv1.begin_split(parent, child)
        kv1.migrate_some(3)
        kv1.abort_split()
        self.assertNotIn(child, kv1.shards())
        self.assertIsNone(kv1.split_progress())
        for i, key in enumerate(keys):
            self.assertEqual(kv1.get(key), i)
            self.assertEqual(kv1.shard_of(key), before[key])

        kv2 = self._open()
        self.assertEqual(kv2.shards(), BASE)
        self.assertIsNone(kv2.split_progress())

    def test_state_from_other_shard_set_rejected(self):
        kv1 = self._open()
        populate(kv1, 10)
        kv1.begin_split(fullest(kv1), "x")
        with self.assertRaises(ValueError):
            ShardedKV(["other-0", "other-1"], state_path=self.path)


class TestConcurrentSplit(unittest.TestCase):
    def test_hot_key_writes_during_migration(self):
        kv = ShardedKV(BASE)
        keys = populate(kv, 200)
        parent = fullest(kv)
        hot_keys = [k for k in keys if kv.shard_of(k) == parent][:20]
        rounds = 50
        kv.begin_split(parent, parent + "-b")

        def writer(key):
            for i in range(rounds):
                kv.put(key, i)

        threads = [threading.Thread(target=writer, args=(k,))
                   for k in hot_keys]
        for t in threads:
            t.start()
        kv.migrate_all(batch=3)
        for t in threads:
            t.join()
        kv.commit_split()
        for key in hot_keys:
            self.assertEqual(kv.get(key), rounds - 1)
        for shard in kv.shards():
            for key in kv.keys_in(shard):
                self.assertEqual(kv.shard_of(key), shard)


if __name__ == "__main__":
    unittest.main()
