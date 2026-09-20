"""ShardedBloomFilter 行为基线：在线添片、跨片查询、整体假阳性率、旧格式与并发写。"""
import os
import tempfile
import threading
import unittest
import warnings

from bloomx import BloomFilter, ShardedBloomFilter
from bloomx.filter import MAGIC as MAGIC_V1
from bloomx.shard import SHARD_MAGIC


def _shard_fp(shard):
    set_bits = bin(int.from_bytes(bytes(shard._bits), "big")).count("1")
    filled = set_bits / shard.num_bits
    return filled ** shard.num_hashes


def _expected_overall(sf):
    survive = 1.0
    for shard in sf.shards:
        survive *= 1.0 - _shard_fp(shard)
    return 1.0 - survive


class TestOnlineGrowth(unittest.TestCase):
    def test_manual_add_shard_keeps_old_shard_intact(self):
        sf = ShardedBloomFilter(shard_capacity=1000, fp_rate=0.01, max_shards=8)
        for i in range(30):
            sf.add("a%d" % i)
        first = sf.shards[0]
        before = bytes(first._bits)

        index = sf.add_shard()
        self.assertEqual(index, 1)
        self.assertEqual(sf.num_shards, 2)
        self.assertIs(sf.shards[0], first)
        self.assertEqual(bytes(first._bits), before)

        for i in range(30):
            sf.add("b%d" % i)
        self.assertEqual(bytes(first._bits), before)
        self.assertEqual(len(first), 30)
        self.assertEqual(len(sf.shards[1]), 30)
        self.assertEqual(len(sf), 60)

    def test_auto_grow_when_active_shard_fills(self):
        sf = ShardedBloomFilter(shard_capacity=50, fp_rate=0.01, max_shards=10)
        for i in range(130):
            sf.add("k%d" % i)
        self.assertGreaterEqual(sf.num_shards, 3)
        self.assertEqual(len(sf), 130)

    def test_add_shard_online_without_stopping_writes(self):
        sf = ShardedBloomFilter(shard_capacity=100000, max_shards=32)
        gate = threading.Event()

        def writer():
            for i in range(2000):
                sf.add("w%d" % i)
                if i == 500:
                    gate.set()

        t = threading.Thread(target=writer)
        t.start()
        gate.wait(1.0)
        sf.add_shard()
        t.join()
        self.assertEqual(len(sf), 2000)
        for i in range(2000):
            self.assertIn("w%d" % i, sf)


class TestCrossShardQuery(unittest.TestCase):
    def test_item_in_any_shard_is_found(self):
        sf = ShardedBloomFilter(shard_capacity=50, fp_rate=0.01, max_shards=10)
        words = ["word-%d" % i for i in range(200)]
        for word in words:
            sf.add(word)
        self.assertGreater(sf.num_shards, 1)
        for word in words:
            self.assertIn(word, sf)

    def test_absent_item_is_absent_after_growth(self):
        sf = ShardedBloomFilter(shard_capacity=100, fp_rate=0.01, max_shards=10)
        for i in range(250):
            sf.add("present-%d" % i)
        self.assertNotIn("definitely-not-written", sf)
        self.assertNotIn("another-missing-key", sf)

    def test_items_distributed_across_shards_all_queryable(self):
        sf = ShardedBloomFilter(shard_capacity=10, fp_rate=0.01, max_shards=20)
        groups = []
        for g in range(4):
            group = ["g%d-k%d" % (g, i) for i in range(10)]
            for word in group:
                sf.add(word)
            groups.append(group)
            if g < 3:
                sf.add_shard()
        self.assertEqual(sf.num_shards, 4)
        for group in groups:
            for word in group:
                self.assertIn(word, sf)


class TestOverallFpRate(unittest.TestCase):
    def test_empty_filter_overall_rate_is_zero(self):
        sf = ShardedBloomFilter(shard_capacity=1000, fp_rate=0.01)
        sf.add_shard()
        self.assertEqual(sf.fp_rate_overall, 0.0)

    def test_overall_rate_combines_every_shard(self):
        sf = ShardedBloomFilter(shard_capacity=200, fp_rate=0.01, max_shards=8)
        for i in range(150):
            sf.add("x%d" % i)
        sf.add_shard()
        for i in range(50):
            sf.add("y%d" % i)
        self.assertEqual(sf.num_shards, 2)
        self.assertAlmostEqual(sf.fp_rate_overall, _expected_overall(sf), places=12)
        # 两片都非空时，整体率高于任意单片率（不是各算各的）。
        rates = [_shard_fp(shard) for shard in sf.shards]
        self.assertGreater(sf.fp_rate_overall, max(rates))

    def test_overall_rate_is_one_number_and_grows_with_fill(self):
        sf = ShardedBloomFilter(shard_capacity=500, fp_rate=0.01, max_shards=4)
        self.assertIsInstance(sf.fp_rate_overall, float)
        for i in range(300):
            sf.add("a%d" % i)
        rate_full_shard = sf.fp_rate_overall
        sf.add_shard()
        for i in range(10):
            sf.add("fresh-%d" % i)
        # 新加的空片只做并集，整体率几乎不变且不退回成单片的数。
        self.assertAlmostEqual(sf.fp_rate_overall, rate_full_shard, places=6)

    def test_overall_rate_matches_empirical_union(self):
        sf = ShardedBloomFilter(shard_capacity=200000, fp_rate=0.01, max_shards=4)
        total = 0
        for g in range(3):
            for i in range(40000):
                sf.add("g%d-item-%d" % (g, i))
            total += 40000
            if g < 2:
                sf.add_shard()
        self.assertEqual(sf.num_shards, 3)
        probes = ["never-added-probe-%d" % i for i in range(20000)]
        false_positives = sum(1 for probe in probes if probe in sf)
        empirical = false_positives / len(probes)
        self.assertAlmostEqual(empirical, sf.fp_rate_overall, delta=0.01)


class TestLegacyFormat(unittest.TestCase):
    def test_reads_v1_single_instance_blob(self):
        legacy = BloomFilter(capacity=1000, fp_rate=0.01)
        for word in ["old", "data", "alpha"]:
            legacy.add(word)
        blob = legacy.to_bytes()
        self.assertTrue(blob.startswith(MAGIC_V1))

        sf = ShardedBloomFilter.from_bytes(blob)
        self.assertEqual(sf.num_shards, 1)
        for word in ["old", "data", "alpha"]:
            self.assertIn(word, sf)
        self.assertNotIn("missing", sf)
        self.assertEqual(len(sf), 3)

    def test_legacy_shard_stays_intact_after_growth(self):
        legacy = BloomFilter(capacity=100, fp_rate=0.01)
        for i in range(20):
            legacy.add("legacy-%d" % i)
        legacy_blob = legacy.to_bytes()

        sf = ShardedBloomFilter.from_bytes(legacy_blob)
        sf.add_shard()
        for i in range(20):
            sf.add("new-%d" % i)

        self.assertEqual(sf.shards[0].to_bytes(), legacy_blob)
        for i in range(20):
            self.assertIn("legacy-%d" % i, sf)
            self.assertIn("new-%d" % i, sf)

    def test_legacy_file_grows_automatically_on_overflow(self):
        legacy = BloomFilter(capacity=100, fp_rate=0.05)
        for i in range(80):
            legacy.add("old-%d" % i)
        sf = ShardedBloomFilter.from_bytes(legacy.to_bytes())
        for i in range(500):
            sf.add("more-%d" % i)
        self.assertGreater(sf.num_shards, 1)
        for i in range(80):
            self.assertIn("old-%d" % i, sf)
        for i in range(500):
            self.assertIn("more-%d" % i, sf)

    def test_v2_roundtrip_and_magic(self):
        sf = ShardedBloomFilter(shard_capacity=200, fp_rate=0.02, max_shards=5)
        for i in range(120):
            sf.add("k%d" % i)
        sf.add_shard()
        for i in range(10):
            sf.add("z%d" % i)
        blob = sf.to_bytes()
        self.assertTrue(blob.startswith(SHARD_MAGIC))

        restored = ShardedBloomFilter.from_bytes(blob)
        self.assertEqual(restored.num_shards, 2)
        self.assertEqual(restored.shard_capacity, 200)
        self.assertEqual(restored.max_shards, 5)
        self.assertAlmostEqual(restored.fp_rate, 0.02)
        self.assertEqual(len(restored), 130)
        for i in range(120):
            self.assertIn("k%d" % i, restored)
        for i in range(10):
            self.assertIn("z%d" % i, restored)
        self.assertEqual(restored.to_bytes(), blob)

    def test_save_and_load_accepts_legacy_file(self):
        legacy = BloomFilter(capacity=500, fp_rate=0.01)
        legacy.add("persisted")
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "bloom.bin")
        with open(path, "wb") as handle:
            handle.write(legacy.to_bytes())

        sf = ShardedBloomFilter.load(path)
        self.assertIn("persisted", sf)
        sf.add_shard()
        sf.add("new-persisted")
        sf.save(path)

        again = ShardedBloomFilter.load(path)
        self.assertTrue(again.to_bytes().startswith(SHARD_MAGIC))
        self.assertEqual(again.num_shards, 2)
        self.assertIn("persisted", again)
        self.assertIn("new-persisted", again)

    def test_bad_blob_rejected(self):
        with self.assertRaises(ValueError):
            ShardedBloomFilter.from_bytes(b"NOPE")
        with self.assertRaises(ValueError):
            ShardedBloomFilter.from_bytes(b"BL")


class TestConcurrentWriteDuringGrowth(unittest.TestCase):
    def test_no_lost_writes_while_shards_are_added(self):
        sf = ShardedBloomFilter(shard_capacity=100000, fp_rate=0.01, max_shards=64)
        writers_done = threading.Event()

        def writer(seed):
            for i in range(3000):
                sf.add("t%d-%d" % (seed, i))

        threads = [threading.Thread(target=writer, args=(seed,)) for seed in range(4)]
        for thread in threads:
            thread.start()

        grower_errors = []

        def grower():
            for _ in range(9):
                try:
                    sf.add_shard()
                except RuntimeError as exc:
                    grower_errors.append(exc)

        grow_thread = threading.Thread(target=grower)
        grow_thread.start()
        for thread in threads:
            thread.join()
        writers_done.set()
        grow_thread.join()

        self.assertEqual(grower_errors, [])
        self.assertEqual(len(sf), 12000)
        for seed in range(4):
            for i in range(3000):
                self.assertIn("t%d-%d" % (seed, i), sf)

    def test_auto_grow_under_concurrent_writers(self):
        sf = ShardedBloomFilter(shard_capacity=100, fp_rate=0.01, max_shards=128)

        def writer(seed):
            for i in range(1000):
                sf.add("c%d-%d" % (seed, i))

        threads = [threading.Thread(target=writer, args=(seed,)) for seed in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(len(sf), 8000)
        self.assertGreater(sf.num_shards, 1)
        for seed in range(8):
            for i in range(1000):
                self.assertIn("c%d-%d" % (seed, i), sf)


class TestMemoryBackstop(unittest.TestCase):
    def test_add_shard_raises_at_max_shards(self):
        sf = ShardedBloomFilter(shard_capacity=1000, max_shards=2)
        sf.add_shard()
        with self.assertRaises(RuntimeError):
            sf.add_shard()
        self.assertEqual(sf.num_shards, 2)

    def test_overflow_keeps_service_alive_and_flags_capped(self):
        sf = ShardedBloomFilter(shard_capacity=50, fp_rate=0.01, max_shards=2)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            for i in range(200):
                sf.add("v%d" % i)
        self.assertTrue(sf.capped)
        self.assertEqual(sf.num_shards, 2)
        self.assertEqual(len(sf), 200)
        self.assertTrue(any(issubclass(w.category, RuntimeWarning) for w in caught))
        for i in range(200):
            self.assertIn("v%d" % i, sf)

    def test_zero_max_shards_means_unlimited(self):
        sf = ShardedBloomFilter(shard_capacity=10, fp_rate=0.01, max_shards=0)
        for _ in range(5):
            sf.add_shard()
        self.assertEqual(sf.num_shards, 6)
        self.assertFalse(sf.capped)


if __name__ == "__main__":
    unittest.main()
