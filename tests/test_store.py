"""ShardedKV 行为基线。

这些断言描述的是线上已经在依赖的语义：同一个键在任何实例上都落到同一片、
分片顺序决定映射结果、各片独立读写、非法分片集合直接拒绝。做在线分裂改造
时它们必须原样全绿，一个字不许改。
"""
import threading
import unittest

from shardstore import ShardedKV


class TestConstruction(unittest.TestCase):
    def test_shards_returns_copy(self):
        kv = ShardedKV(["s0", "s1"])
        got = kv.shards()
        self.assertEqual(got, ["s0", "s1"])
        got.append("s2")
        self.assertEqual(kv.shards(), ["s0", "s1"])

    def test_len_is_shard_count(self):
        self.assertEqual(len(ShardedKV(["s0", "s1", "s2"])), 3)

    def test_rejects_empty_shard_set(self):
        with self.assertRaises(ValueError):
            ShardedKV([])

    def test_rejects_duplicate_shard_id(self):
        with self.assertRaises(ValueError):
            ShardedKV(["s0", "s0"])

    def test_rejects_empty_shard_id(self):
        with self.assertRaises(ValueError):
            ShardedKV(["s0", ""])


class TestRouting(unittest.TestCase):
    def setUp(self):
        self.kv = ShardedKV(["shard-0", "shard-1", "shard-2"])

    def test_pinned_slots_are_stable(self):
        self.assertEqual(self.kv.shard_of("order:1"), "shard-0")
        self.assertEqual(self.kv.shard_of("order:7"), "shard-2")
        self.assertEqual(self.kv.shard_of("order:42"), "shard-2")

    def test_route_is_deterministic(self):
        self.assertEqual(self.kv.shard_of("order:1"), self.kv.shard_of("order:1"))

    def test_route_only_depends_on_key_and_shard_set(self):
        other = ShardedKV(["shard-0", "shard-1", "shard-2"])
        for key in ["order:%d" % i for i in range(50)]:
            self.assertEqual(self.kv.shard_of(key), other.shard_of(key))

    def test_route_always_names_a_known_shard(self):
        for key in ["order:%d" % i for i in range(200)]:
            self.assertIn(self.kv.shard_of(key), self.kv.shards())

    def test_accepts_str_bytes_and_int(self):
        self.assertEqual(self.kv.shard_of(b"\x00\x01"), self.kv.shard_of(b"\x00\x01"))
        self.assertIn(self.kv.shard_of(12345), self.kv.shards())

    def test_shard_order_changes_the_mapping(self):
        flipped = ShardedKV(["shard-2", "shard-1", "shard-0"])
        moved = [k for k in ["order:%d" % i for i in range(50)]
                 if self.kv.shard_of(k) != flipped.shard_of(k)]
        self.assertTrue(moved)


class TestReadWrite(unittest.TestCase):
    def setUp(self):
        self.kv = ShardedKV(["shard-0", "shard-1", "shard-2"])

    def test_put_returns_the_owning_shard(self):
        self.assertEqual(self.kv.put("order:1", 100), self.kv.shard_of("order:1"))

    def test_roundtrip(self):
        self.kv.put("order:1", {"qty": 3})
        self.assertEqual(self.kv.get("order:1"), {"qty": 3})

    def test_missing_key_returns_default(self):
        self.assertIsNone(self.kv.get("order:999"))
        self.assertEqual(self.kv.get("order:999", -1), -1)

    def test_overwrite_keeps_one_entry(self):
        self.kv.put("order:2", 1)
        self.kv.put("order:2", 2)
        self.assertEqual(self.kv.get("order:2"), 2)
        self.assertEqual(self.kv.size(self.kv.shard_of("order:2")), 1)

    def test_delete_reports_whether_it_hit(self):
        self.kv.put("order:3", 7)
        self.assertTrue(self.kv.delete("order:3"))
        self.assertFalse(self.kv.delete("order:3"))
        self.assertIsNone(self.kv.get("order:3"))

    def test_keys_land_only_on_their_shard(self):
        for i in range(60):
            self.kv.put("order:%d" % i, i)
        for shard in self.kv.shards():
            for key in self.kv.keys_in(shard):
                self.assertEqual(self.kv.shard_of(key), shard)


class TestDistribution(unittest.TestCase):
    def setUp(self):
        self.kv = ShardedKV(["shard-0", "shard-1", "shard-2"])

    def test_keys_in_is_a_copy(self):
        self.kv.put("order:1", 1)
        keys = self.kv.keys_in(self.kv.shard_of("order:1"))
        keys.append("junk")
        self.assertNotIn("junk", self.kv.keys_in(self.kv.shard_of("order:1")))

    def test_keys_in_partitions_the_keys(self):
        keys = ["order:%d" % i for i in range(100)]
        for k in keys:
            self.kv.put(k, 1)
        buckets = [self.kv.keys_in(s) for s in self.kv.shards()]
        self.assertEqual(sorted(k for b in buckets for k in b), sorted(keys))

    def test_keys_in_rejects_unknown_shard(self):
        with self.assertRaises(KeyError):
            self.kv.keys_in("nope")

    def test_size_rejects_unknown_shard(self):
        with self.assertRaises(KeyError):
            self.kv.size("nope")

    def test_distribution_counts_every_key(self):
        for i in range(100):
            self.kv.put("order:%d" % i, i)
        dist = self.kv.distribution()
        self.assertEqual(set(dist), set(self.kv.shards()))
        self.assertEqual(sum(dist.values()), 100)
        self.assertEqual(self.kv.total(), 100)

    def test_distribution_starts_every_shard_at_zero(self):
        self.assertEqual(self.kv.distribution(),
                         {"shard-0": 0, "shard-1": 0, "shard-2": 0})

    def test_total_of_empty_store_is_zero(self):
        self.assertEqual(self.kv.total(), 0)


class TestConcurrency(unittest.TestCase):
    def test_parallel_puts_do_not_lose_keys(self):
        kv = ShardedKV(["s0", "s1", "s2"])
        workers = 8
        per_worker = 200

        def run(w):
            for i in range(per_worker):
                kv.put("w%d-k%d" % (w, i), i)

        threads = [threading.Thread(target=run, args=(w,)) for w in range(workers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(kv.total(), workers * per_worker)


if __name__ == "__main__":
    unittest.main()
