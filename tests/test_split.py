"""在线分裂行为测试。

覆盖四件最怕的事：搬移期间读写两边都认、进度可见且可从断点续搬、
提交是一次性原子切换（不提前路由）、失败可以整体回退；以及连续分裂
时路由不退化、别片一个键不动。
"""
import json
import os
import tempfile
import unittest

from shardstore import ShardedKV
from shardstore.store import _digest


def make_store(shards=("shard-0", "shard-1", "shard-2")):
    tmp = tempfile.mkdtemp()
    state_path = os.path.join(tmp, "split-state.json")
    return ShardedKV(list(shards), state_path=state_path), state_path


def seed(kv, n=300):
    keys = ["order:%d" % i for i in range(n)]
    for i, key in enumerate(keys):
        kv.put(key, i)
    return keys


def warm_restart(kv, base_shards):
    """模拟进程热重启：内存数据保留，路由与游标从状态文件重建。"""
    kv._routing = kv._load_state(list(base_shards))
    return kv


def partition(kv, keys, old, new):
    bit = kv._routing.mig["bit"]
    bucket = kv._routing.desc[old][0]
    n = kv._routing.bucket_count
    in_old = [k for k in keys if _digest(k) % n == bucket]
    moving = [k for k in in_old if _digest(k) & bit]
    staying = [k for k in in_old if not (_digest(k) & bit)]
    return moving, staying


class TestSplitBasics(unittest.TestCase):
    def setUp(self):
        self.kv, _ = make_store()
        self.keys = seed(self.kv)
        self.hot = "shard-0"

    def test_split_divides_half_by_hash_bit_and_leaves_others_alone(self):
        before = self.kv.distribution()
        progress = self.kv.begin_split(self.hot, "shard-0b", batch_size=50)
        self.assertEqual(set(self.kv.shards()),
                         {"shard-0", "shard-1", "shard-2", "shard-0b"})
        self.assertEqual(progress["scanned"], 0)
        self.assertFalse(progress["done"])
        other_sizes = {s: before[s] for s in ("shard-1", "shard-2")}
        self.assertEqual({s: self.kv.size(s) for s in other_sizes}, other_sizes)
        self.assertEqual(progress["half_total"],
                         sum(1 for k in self.kv.keys_in(self.hot)
                             if self.kv.shard_of(k) == "shard-0b"))

    def test_route_points_moving_half_at_new_shard_and_staying_at_old(self):
        self.kv.begin_split(self.hot, "shard-0b")
        moving, staying = partition(self.kv, self.keys, self.hot, "shard-0b")
        self.assertTrue(moving and staying)
        for key in moving:
            self.assertEqual(self.kv.shard_of(key), "shard-0b")
        for key in staying:
            self.assertEqual(self.kv.shard_of(key), self.hot)


class TestDualWriteAndReadFallback(unittest.TestCase):
    def setUp(self):
        self.kv, _ = make_store()
        self.keys = seed(self.kv)
        self.hot = "shard-0"
        self.kv.begin_split(self.hot, "shard-0b", batch_size=13)
        self.moving, self.staying = partition(
            self.kv, self.keys, self.hot, "shard-0b")

    def test_writes_land_on_both_sides_during_migration(self):
        key = self.moving[0]
        self.kv.put(key, "dual")
        self.assertEqual(self.kv.get(key), "dual")
        self.assertEqual(self.kv.keys_in("shard-0b").count(key)
                         + self.kv.keys_in(self.hot).count(key), 2)

    def test_read_falls_back_to_old_shard_before_copy(self):
        key = None
        for candidate in self.moving:
            if candidate not in self.kv.keys_in("shard-0b"):
                key = candidate
                break
        self.assertIsNotNone(key)
        self.assertEqual(self.kv.get(key),
                         int(key.split(":")[1]))  # 新片没搬，回退老片捞
        self.assertIsNone(self.kv.get("order:999999"))

    def test_read_prefers_new_shard_value(self):
        key = self.moving[0]
        self.kv.migrate_until_done()
        self.kv.put(key, "freshest")
        self.assertEqual(self.kv.get(key), "freshest")

    def test_new_key_of_moving_half_is_dual_written(self):
        self.kv.put("order:fresh", "x")
        if self.kv.shard_of("order:fresh") == "shard-0b":
            self.assertIn("order:fresh", self.kv.keys_in("shard-0b"))
            self.assertIn("order:fresh", self.kv.keys_in(self.hot))
        self.assertEqual(self.kv.get("order:fresh"), "x")

    def test_delete_during_migration_removes_both_copies(self):
        key = self.moving[0]
        self.kv.put(key, "v")
        self.assertTrue(self.kv.delete(key))
        self.assertNotIn(key, self.kv.keys_in("shard-0b"))
        self.assertNotIn(key, self.kv.keys_in(self.hot))
        self.assertIsNone(self.kv.get(key))
        self.assertFalse(self.kv.delete(key))


class TestProgressAndResume(unittest.TestCase):
    def setUp(self):
        self.kv, self.state_path = make_store()
        self.keys = seed(self.kv)
        self.kv.begin_split("shard-0", "shard-0b", batch_size=20)

    def test_progress_advances_per_batch_and_reports_done(self):
        first = self.kv.split_progress()
        self.kv.migrate_batch()
        second = self.kv.split_progress()
        self.assertEqual(second["scanned"], first["scanned"] + 20)
        self.assertGreaterEqual(second["moved"], 0)
        while not self.kv.split_progress()["done"]:
            self.kv.migrate_batch()
        progress = self.kv.split_progress()
        self.assertEqual(progress["remaining_snapshot"], 0)
        self.assertEqual(progress["scanned"], progress["snapshot_size"])

    def test_restart_resumes_from_cursor_without_restarting(self):
        for _ in range(3):
            self.kv.migrate_batch()
        saved = self.kv.split_progress()
        payload = json.load(open(self.state_path, encoding="utf-8"))
        self.assertEqual(payload["migrating"]["cursor"], saved["scanned"])

        warm_restart(self.kv, ("shard-0", "shard-1", "shard-2"))
        resumed = self.kv.split_progress()
        self.assertEqual(resumed["scanned"], saved["scanned"])
        self.assertEqual(resumed["moved"], saved["moved"])

        copied_once_more = self.kv.migrate_batch()
        self.assertEqual(self.kv.split_progress()["scanned"],
                         saved["scanned"] + 20)
        self.assertGreater(copied_once_more, 0)

    def test_hot_key_rewritten_after_restart_is_not_lost(self):
        key = partition(self.kv, self.keys, "shard-0", "shard-0b")[0][0]
        self.kv.migrate_batch()
        self.kv.put(key, "hot-rewrite")
        warm_restart(self.kv, ("shard-0", "shard-1", "shard-2"))
        self.kv.migrate_until_done()
        self.kv.commit_split()
        self.assertEqual(self.kv.get(key), "hot-rewrite")


class TestCommitAndRoutingCutover(unittest.TestCase):
    def setUp(self):
        self.kv, self.state_path = make_store()
        self.keys = seed(self.kv)
        self.kv.begin_split("shard-0", "shard-0b", batch_size=25)
        self.moving, self.staying = partition(
            self.kv, self.keys, "shard-0", "shard-0b")

    def test_commit_before_catchup_is_refused(self):
        with self.assertRaises(RuntimeError):
            self.kv.commit_split()
        self.assertIsNotNone(self.kv.split_progress())  # 路由没被提前切

    def test_routing_does_not_switch_early(self):
        mid = self.kv._routing
        self.kv.migrate_batch()
        self.assertIs(self.kv._routing, mid)  # 搬移绝不换路由

    def test_commit_copies_half_and_cleans_old_copy(self):
        self.kv.migrate_until_done()
        shards = self.kv.commit_split()
        self.assertEqual(shards, ["shard-0", "shard-1", "shard-2", "shard-0b"])
        self.assertIsNone(self.kv.split_progress())
        for key in self.moving:
            self.assertEqual(self.kv.shard_of(key), "shard-0b")
            self.assertNotIn(key, self.kv.keys_in("shard-0"))
            self.assertIn(key, self.kv.keys_in("shard-0b"))
            self.assertEqual(self.kv.get(key), int(key.split(":")[1]))
        for key in self.staying:
            self.assertEqual(self.kv.shard_of(key), "shard-0")
            self.assertIn(key, self.kv.keys_in("shard-0"))
        self.assertEqual(self.kv.total(), len(self.keys))
        payload = json.load(open(self.state_path, encoding="utf-8"))
        self.assertIsNone(payload["migrating"])

    def test_commit_self_heals_data_lost_by_a_cold_restart(self):
        self.kv.migrate_until_done()
        self.kv._data["shard-0b"].clear()  # 重启后新片内存为空，老片仍全量
        self.kv.commit_split()
        for key in self.moving:
            self.assertEqual(self.kv.get(key), int(key.split(":")[1]))

    def test_late_write_before_commit_is_caught_up(self):
        self.kv.migrate_until_done()
        key = self.moving[1]
        self.kv.put(key, "last-second")
        self.kv.commit_split()
        self.assertEqual(self.kv.get(key), "last-second")


class TestRollback(unittest.TestCase):
    def setUp(self):
        self.kv, self.state_path = make_store()
        self.keys = seed(self.kv)

    def test_rollback_discards_new_shard_and_restores_old_route(self):
        before = {k: self.kv.shard_of(k) for k in self.keys}
        self.kv.begin_split("shard-0", "shard-0b", batch_size=40)
        moving, _ = partition(self.kv, self.keys, "shard-0", "shard-0b")
        self.kv.migrate_until_done()
        self.kv.put(moving[0], "mid-write")
        shards = self.kv.rollback_split()
        self.assertEqual(shards, ["shard-0", "shard-1", "shard-2"])
        self.assertNotIn("shard-0b", self.kv.shards())
        for key in self.keys:
            self.assertEqual(self.kv.shard_of(key), before[key])
            if key != moving[0]:
                self.assertEqual(self.kv.get(key), int(key.split(":")[1]))
        self.assertEqual(self.kv.get(moving[0]), "mid-write")  # 老片全量副本
        self.assertIsNone(self.kv.split_progress())

    def test_rollback_state_survives_restart(self):
        self.kv.begin_split("shard-0", "shard-0b")
        self.kv.migrate_batch()
        self.kv.rollback_split()
        reopened = ShardedKV(["shard-0", "shard-1", "shard-2"],
                             state_path=self.state_path)
        self.assertEqual(reopened.shards(),
                         ["shard-0", "shard-1", "shard-2"])
        self.assertIsNone(reopened.split_progress())

    def test_split_again_after_rollback_works(self):
        self.kv.begin_split("shard-0", "shard-0b", batch_size=10)
        self.kv.rollback_split()
        self.kv.begin_split("shard-0", "shard-0c", batch_size=10)
        self.kv.migrate_until_done()
        self.kv.commit_split()
        self.assertEqual(self.kv.shards()[-1], "shard-0c")


class TestRepeatedSplits(unittest.TestCase):
    def test_route_stays_partitioned_through_two_splits(self):
        kv, _ = make_store()
        keys = seed(kv, n=600)
        kv.begin_split("shard-0", "shard-0b", batch_size=50)
        kv.migrate_until_done()
        kv.commit_split()
        kv.begin_split("shard-0b", "shard-0b2", batch_size=50)
        self.assertTrue(kv.split_progress())
        kv.migrate_until_done()
        kv.commit_split()

        owners = {key: kv.shard_of(key) for key in keys}
        self.assertEqual(set(owners.values()),
                         {"shard-0", "shard-1", "shard-2",
                          "shard-0b", "shard-0b2"})
        for key in keys:
            self.assertEqual(kv.get(key), int(key.split(":")[1]))
        covered = (set(kv.keys_in("shard-0b"))
                   | set(kv.keys_in("shard-0b2")))
        self.assertTrue(covered)
        self.assertTrue(covered.isdisjoint(kv.keys_in("shard-0")))
        self.assertEqual(kv.total(), len(keys))

    def test_other_shards_never_move_during_split(self):
        kv, _ = make_store(("s0", "s1", "s2", "s3"))
        keys = ["k%d" % i for i in range(400)]
        for key in keys:
            kv.put(key, 1)
        untouched_before = {s: kv.keys_in(s) for s in ("s1", "s2", "s3")}
        kv.begin_split("s0", "s0b", batch_size=31)
        kv.migrate_until_done()
        kv.commit_split()
        for shard in ("s1", "s2", "s3"):
            self.assertEqual(kv.keys_in(shard), untouched_before[shard])


class TestSplitGuards(unittest.TestCase):
    def setUp(self):
        self.kv, _ = make_store()

    def test_only_one_split_at_a_time(self):
        self.kv.begin_split("shard-0", "shard-0b")
        with self.assertRaises(RuntimeError):
            self.kv.begin_split("shard-1", "shard-1b")

    def test_migrate_and_commit_without_split_raise(self):
        with self.assertRaises(RuntimeError):
            self.kv.migrate_batch()
        with self.assertRaises(RuntimeError):
            self.kv.commit_split()
        with self.assertRaises(RuntimeError):
            self.kv.rollback_split()

    def test_begin_validates_shard_names(self):
        with self.assertRaises(KeyError):
            self.kv.begin_split("nope", "nope-b")
        with self.assertRaises(ValueError):
            self.kv.begin_split("shard-0", "shard-0")
        with self.assertRaises(ValueError):
            self.kv.begin_split("shard-0", "")


class TestSplitConcurrency(unittest.TestCase):
    def test_traffic_during_online_split_loses_nothing(self):
        import threading
        kv, _ = make_store(("a", "b", "c"))
        keys = ["k%d" % i for i in range(1000)]
        for key in keys:
            kv.put(key, 0)
        kv.begin_split("a", "a2", batch_size=7)

        stop = threading.Event()

        def writer(worker):
            i = worker
            while not stop.is_set():
                key = keys[i % len(keys)]
                kv.put(key, i)
                self.assertIsNotNone(kv.get(key))
                i += 3

        threads = [threading.Thread(target=writer, args=(w,)) for w in range(6)]
        for thread in threads:
            thread.start()
        while not kv.split_progress()["done"]:
            kv.migrate_batch()
        kv.commit_split()
        stop.set()
        for thread in threads:
            thread.join()

        for key in keys:
            self.assertIsNotNone(kv.get(key))
        self.assertEqual(kv.total(), len(keys))


if __name__ == "__main__":
    unittest.main()
