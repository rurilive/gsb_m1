"""在线分裂行为测试。

覆盖四条硬语义：分裂期间读先问新片、没有再回老片，待搬键写两边；
进度可见且游标落检查点，重启从断点续搬；提交是一次性原子换路由，
回退是合回老片整体撤销；劈完还能接着劈，片数涨了路由不退化。
"""
import os
import shutil
import tempfile
import threading
import unittest

from shardstore import ShardedKV


class TestSplitRouting(unittest.TestCase):
    def setUp(self):
        self.kv = ShardedKV(["s0", "s1", "s2"])
        for i in range(90):
            self.kv.put("order:%d" % i, i)

    def test_begin_split_keeps_routing_on_old_shard(self):
        split = self.kv.begin_split("s0", "s0b")
        self.assertEqual(self.kv.active_split(), split)
        for key in self.kv.keys_in("s0"):
            self.assertEqual(self.kv.shard_of(key), "s0")
        self.assertEqual(len(self.kv), 3)

    def test_mover_predicate_splits_the_shard_in_half_by_hash(self):
        split = self.kv.begin_split("s0", "s0b")
        keys = self.kv.keys_in("s0")
        movers = [k for k in keys if split.is_mover(k)]
        stayers = [k for k in keys if not split.is_mover(k)]
        self.assertTrue(movers)
        self.assertTrue(stayers)
        self.assertEqual(set(movers) | set(stayers), set(keys))

    def test_other_shards_are_not_touched_by_split(self):
        before = {s: self.kv.keys_in(s) for s in ["s1", "s2"]}
        split = self.kv.begin_split("s0", "s0b")
        split.drain()
        split.commit()
        self.assertEqual(self.kv.keys_in("s1"), before["s1"])
        self.assertEqual(self.kv.keys_in("s2"), before["s2"])

    def test_begin_split_rejects_unknown_or_duplicate_shard(self):
        with self.assertRaises(KeyError):
            self.kv.begin_split("nope")
        with self.assertRaises(ValueError):
            self.kv.begin_split("s0", "s1")
        self.kv.begin_split("s0", "s0b")
        with self.assertRaises(RuntimeError):
            self.kv.begin_split("s1", "s1b")


class TestDualReadWrite(unittest.TestCase):
    def setUp(self):
        self.kv = ShardedKV(["s0", "s1", "s2"])
        for i in range(90):
            self.kv.put("order:%d" % i, i)
        self.split = self.kv.begin_split("s0", "s0b")
        self.movers = [k for k in self.kv.keys_in("s0")
                       if self.split.is_mover(k)]
        self.stayers = [k for k in self.kv.keys_in("s0")
                        if not self.split.is_mover(k)]

    def test_put_of_mover_lands_on_both_sides(self):
        key = self.movers[0]
        self.kv.put(key, 1234)
        with self.split.lock:
            self.assertEqual(self.split.data[key], 1234)
        self.assertEqual(self.kv.get(key), 1234)

    def test_put_of_stayer_lands_only_on_old_side(self):
        key = self.stayers[0]
        self.kv.put(key, 4321)
        with self.split.lock:
            self.assertNotIn(key, self.split.data)
        self.assertEqual(self.kv.get(key), 4321)

    def test_read_asks_new_side_first(self):
        key = self.movers[0]
        self.split.migrate(1)
        with self.split.lock, self.kv._locks["s0"]:
            self.assertIn(key, self.split.data)
            self.assertNotIn(key, self.kv._data["s0"])
        self.assertEqual(self.kv.get(key), int(key.split(":")[1]))

    def test_read_falls_back_to_old_side(self):
        key = self.movers[1]
        self.assertEqual(self.kv.get(key), int(key.split(":")[1]))
        with self.split.lock:
            self.assertNotIn(key, self.split.data)

    def test_delete_mover_during_split_hits_both_sides(self):
        key = self.movers[0]
        self.kv.put(key, "v")
        self.assertTrue(self.kv.delete(key))
        self.assertIsNone(self.kv.get(key))
        with self.split.lock:
            self.assertNotIn(key, self.split.data)
        self.assertFalse(self.kv.delete(key))

    def test_unmigrated_write_does_not_become_an_orphan(self):
        key = next(k for k in self.movers)
        self.kv.put(key, "late")
        # 未搬的键老片里必须还有一份，读回退捞得到，提交时原样跟过去。
        self.assertEqual(self.kv.get(key), "late")
        with self.kv._locks["s0"]:
            self.assertEqual(self.kv._data["s0"][key], "late")
        self.split.drain()
        self.split.commit()
        self.assertEqual(self.kv.get(key), "late")


class TestProgress(unittest.TestCase):
    def test_progress_counts_moved_and_remaining(self):
        kv = ShardedKV(["s0", "s1", "s2"])
        for i in range(60):
            kv.put("k:%d" % i, i)
        split = kv.begin_split("s0", "s0b")
        movers = [k for k in kv.keys_in("s0") if split.is_mover(k)]
        progress = split.progress()
        self.assertEqual(progress["moved"], 0)
        self.assertEqual(progress["remaining"], len(movers))
        self.assertEqual(progress["total"], len(movers))
        self.assertEqual(progress["fraction"], 0.0)
        split.migrate(3)
        progress = split.progress()
        self.assertEqual(progress["moved"], 3)
        self.assertEqual(progress["remaining"], len(movers) - 3)
        split.drain()
        progress = split.progress()
        self.assertEqual(progress["moved"], len(movers))
        self.assertEqual(progress["remaining"], 0)
        self.assertEqual(progress["fraction"], 1.0)

    def test_hot_key_rewritten_after_move_is_swept_at_commit(self):
        kv = ShardedKV(["s0", "s1", "s2"])
        for i in range(30):
            kv.put("k%d" % i, 0)
        split = kv.begin_split("s0", "s0b")
        hot = next(k for k in kv.keys_in("s0") if split.is_mover(k))
        split.drain()
        kv.put(hot, 1)
        self.assertGreaterEqual(split.progress()["remaining"], 1)
        split.commit()
        self.assertEqual(kv.get(hot), 1)
        self.assertEqual(kv.shard_of(hot), "s0b")


class TestCommit(unittest.TestCase):
    def setUp(self):
        self.kv = ShardedKV(["s0", "s1", "s2"])
        for i in range(90):
            self.kv.put("order:%d" % i, i)
        self.split = self.kv.begin_split("s0", "s0b")
        self.movers = [k for k in self.kv.keys_in("s0")
                       if self.split.is_mover(k)]
        self.stayers = [k for k in self.kv.keys_in("s0")
                        if not self.split.is_mover(k)]

    def test_commit_promotes_new_shard_and_moves_ownership(self):
        self.split.drain()
        self.split.commit()
        self.assertIsNone(self.kv.active_split())
        self.assertEqual(self.kv.shards(), ["s0", "s1", "s2", "s0b"])
        self.assertEqual(len(self.kv), 4)
        for key in self.movers:
            self.assertEqual(self.kv.shard_of(key), "s0b")
        for key in self.stayers:
            self.assertEqual(self.kv.shard_of(key), "s0")
        self.assertEqual(self.kv.total(), 90)

    def test_commit_partitions_keys_without_loss_or_duplication(self):
        self.split.drain()
        self.split.commit()
        all_keys = sorted(k for s in self.kv.shards()
                          for k in self.kv.keys_in(s))
        self.assertEqual(all_keys, sorted("order:%d" % i for i in range(90)))
        self.assertEqual(set(self.kv.keys_in("s0")), set(self.stayers))
        self.assertEqual(set(self.kv.keys_in("s0b")), set(self.movers))

    def test_all_values_remain_readable_after_commit(self):
        self.split.drain()
        self.split.commit()
        for i in range(90):
            self.assertEqual(self.kv.get("order:%d" % i), i)

    def test_routing_for_other_shards_is_unchanged_after_commit(self):
        before = {k: self.kv.shard_of(k)
                  for k in self.kv.keys_in("s1") + self.kv.keys_in("s2")}
        self.split.drain()
        self.split.commit()
        for key, owner in before.items():
            self.assertEqual(self.kv.shard_of(key), owner)


class TestAbort(unittest.TestCase):
    def test_abort_merges_new_back_into_old_and_drops_split(self):
        kv = ShardedKV(["s0", "s1", "s2"])
        snapshot = {}
        for i in range(60):
            key = "order:%d" % i
            kv.put(key, i)
            snapshot[key] = i
        split = kv.begin_split("s0", "s0b")
        split.migrate(4)
        movers = [k for k in snapshot if split.is_mover(k)]
        kv.put(movers[0], "abort-value")
        split.abort()
        self.assertIsNone(kv.active_split())
        self.assertEqual(kv.shards(), ["s0", "s1", "s2"])
        self.assertEqual(kv.get(movers[0]), "abort-value")
        for key, value in snapshot.items():
            if key == movers[0]:
                continue
            self.assertEqual(kv.get(key), value)
        self.assertEqual(kv.total(), 60)

    def test_abort_then_resplit_works_from_scratch(self):
        kv = ShardedKV(["s0", "s1", "s2"])
        for i in range(30):
            kv.put("k%d" % i, i)
        split = kv.begin_split("s0", "s0b")
        split.migrate(2)
        split.abort()
        split = kv.begin_split("s0", "s0c")
        self.assertEqual(split.progress()["moved"], 0)
        split.drain()
        split.commit()
        self.assertEqual(kv.total(), 30)


class TestDurableResume(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="shardstore-")
        self.handles = []

    def tearDown(self):
        for handle in self.handles:
            handle.close()
        shutil.rmtree(self.dir, ignore_errors=True)

    def _store(self, shards):
        kv = ShardedKV(shards, state_dir=self.dir)
        self.handles.append(kv)
        return kv

    def _open(self):
        kv = ShardedKV.open(self.dir)
        self.handles.append(kv)
        return kv

    def test_reopen_without_split_replays_wal(self):
        kv = self._store(["s0", "s1", "s2"])
        kv.put("order:1", {"qty": 3})
        kv.put("order:7", [1, 2])
        kv.delete("order:7")
        reopened = self._open()
        self.assertEqual(reopened.get("order:1"), {"qty": 3})
        self.assertIsNone(reopened.get("order:7"))

    def test_resume_continues_from_checkpoint(self):
        kv = self._store(["s0", "s1", "s2"])
        for i in range(60):
            kv.put("order:%d" % i, i)
        split = kv.begin_split("s0", "s0b")
        movers = [k for k in kv.keys_in("s0") if split.is_mover(k)]
        split.migrate(4)
        progress_before = split.progress()

        reopened = self._open()
        split2 = reopened.active_split()
        self.assertIsNotNone(split2)
        self.assertEqual(split2.old, "s0")
        self.assertEqual(split2.new, "s0b")
        self.assertEqual(split2.progress(), progress_before)
        split2.drain()
        split2.commit()
        self.assertEqual(reopened.total(), 60)
        for key in movers:
            self.assertEqual(reopened.shard_of(key), "s0b")
            self.assertEqual(reopened.get(key), int(key.split(":")[1]))

    def test_moved_keys_are_not_moved_again_after_resume(self):
        kv = self._store(["s0", "s1", "s2"])
        for i in range(40):
            kv.put("k%d" % i, i)
        split = kv.begin_split("s1", "s1b")
        self.assertEqual(split.migrate(3), 3)
        done_before = set(split.done)

        reopened = self._open()
        split2 = reopened.active_split()
        self.assertTrue(done_before <= split2.done)
        with split2.lock, reopened._locks["s1"]:
            for key in done_before:
                self.assertIn(key, split2.data)
                self.assertNotIn(key, reopened._data["s1"])

    def test_concurrent_writes_before_crash_are_replayed_on_both_sides(self):
        kv = self._store(["s0", "s1", "s2"])
        for i in range(30):
            kv.put("k%d" % i, i)
        split = kv.begin_split("s0", "s0b")
        hot = next(k for k in kv.keys_in("s0") if split.is_mover(k))
        split.migrate(2)
        kv.put(hot, "fresh")

        reopened = self._open()
        self.assertEqual(reopened.get(hot), "fresh")
        split2 = reopened.active_split()
        with split2.lock:
            self.assertEqual(split2.data.get(hot), "fresh")
        split2.drain()
        split2.commit()
        self.assertEqual(reopened.get(hot), "fresh")

    def test_commit_is_durable_and_checkpoint_is_cleaned(self):
        kv = self._store(["s0", "s1", "s2"])
        for i in range(30):
            kv.put("k%d" % i, i)
        split = kv.begin_split("s0", "s0b")
        split.drain()
        split.commit()
        self.assertFalse(os.path.exists(os.path.join(self.dir, "split.cp.json")))
        reopened = self._open()
        self.assertIsNone(reopened.active_split())
        self.assertEqual(reopened.shards(), ["s0", "s1", "s2", "s0b"])
        self.assertEqual(reopened.total(), 30)

    def test_abort_is_durable_after_reopen(self):
        kv = self._store(["s0", "s1", "s2"])
        for i in range(20):
            kv.put("k%d" % i, i)
        split = kv.begin_split("s2", "s2b")
        split.migrate(2)
        split.abort()
        reopened = self._open()
        self.assertIsNone(reopened.active_split())
        self.assertEqual(reopened.total(), 20)
        for i in range(20):
            self.assertEqual(reopened.get("k%d" % i), i)


class TestRepeatedSplits(unittest.TestCase):
    def _check_partition(self, kv):
        keys = ["order:%d" % i for i in range(120)]
        seen = set()
        for shard in kv.shards():
            bucket = set(kv.keys_in(shard))
            self.assertTrue(seen.isdisjoint(bucket))
            seen |= bucket
            for key in bucket:
                self.assertEqual(kv.shard_of(key), shard)
        self.assertEqual(seen, set(keys))

    def test_split_after_split_does_not_degrade_routing(self):
        kv = ShardedKV(["s0", "s1", "s2"])
        keys = ["order:%d" % i for i in range(120)]
        for key in keys:
            kv.put(key, key)

        split = kv.begin_split("s0", "s0b")
        split.drain()
        split.commit()
        self._check_partition(kv)

        split = kv.begin_split("s0b", "s0c")
        s0b_keys = kv.keys_in("s0b")
        movers = [k for k in s0b_keys if split.is_mover(k)]
        self.assertTrue(movers)
        self.assertTrue(any(not split.is_mover(k) for k in s0b_keys))
        split.drain()
        split.commit()
        self._check_partition(kv)
        for key in movers:
            self.assertEqual(kv.shard_of(key), "s0c")
            self.assertEqual(kv.get(key), key)
        for key in keys:
            self.assertEqual(kv.get(key), key)
        self.assertEqual(kv.total(), 120)

    def test_split_other_shard_after_first_split_is_isolated(self):
        kv = ShardedKV(["s0", "s1", "s2"])
        for i in range(90):
            kv.put("order:%d" % i, i)
        split = kv.begin_split("s0", "s0b")
        split.drain()
        split.commit()
        first = {s: kv.keys_in(s) for s in ["s0", "s0b"]}

        split = kv.begin_split("s1", "s1b")
        split.drain()
        split.commit()
        self.assertEqual(kv.keys_in("s0"), first["s0"])
        self.assertEqual(kv.keys_in("s0b"), first["s0b"])
        self.assertEqual(kv.total(), 90)


class TestSplitConcurrency(unittest.TestCase):
    def test_traffic_during_migration_loses_nothing(self):
        kv = ShardedKV(["s0", "s1", "s2"])
        keys = ["w%d-k%d" % (w, i) for w in range(6) for i in range(40)]
        for key in keys:
            kv.put(key, 0)
        split = kv.begin_split("s0", "s0b")

        stop = threading.Event()

        def writer():
            rounds = 0
            while not stop.is_set():
                key = keys[(rounds * 7) % len(keys)]
                kv.put(key, rounds)
                kv.get(key)
                rounds += 1

        threads = [threading.Thread(target=writer) for _ in range(4)]
        for thread in threads:
            thread.start()
        while split.progress()["fraction"] < 1.0:
            split.migrate(8)
        split.commit()
        stop.set()
        for thread in threads:
            thread.join()

        self.assertEqual(kv.total(), len(keys))
        all_keys = [k for s in kv.shards() for k in kv.keys_in(s)]
        self.assertEqual(sorted(all_keys), sorted(keys))
        for key in keys:
            self.assertEqual(kv.shard_of(key),
                             "s0b" if key in kv.keys_in("s0b") else
                             [s for s in kv.shards() if s != "s0b"
                              and key in kv.keys_in(s)][0])


if __name__ == "__main__":
    unittest.main()
