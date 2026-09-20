"""分片布隆过滤器新行为：在线添片、跨片查询、整体假阳性率、
老格式读回、添片期间并发写、内存兜底与磁盘状态。"""
import math
import os
import tempfile
import threading
import unittest

from bloomx import BloomFilter, ShardFullError, ShardedBloomFilter
from bloomx.filter import MAGIC as LEGACY_MAGIC
from bloomx.shard import MAGIC


def _fill(sf, start, count):
    for i in range(start, start + count):
        sf.add("k%d" % i)


class TestOnlineGrowth(unittest.TestCase):
    def test_auto_adds_shard_when_head_fills(self):
        sf = ShardedBloomFilter(capacity=100, fp_rate=0.01, max_shards=8)
        self.assertEqual(sf.num_shards, 1)
        _fill(sf, 0, 100)
        self.assertEqual(sf.num_shards, 1)
        sf.add("one-more")
        self.assertEqual(sf.num_shards, 2)
        _fill(sf, 101, 100)
        self.assertEqual(sf.num_shards, 3)
        self.assertEqual(len(sf), 201)

    def test_explicit_add_shard_freezes_old(self):
        sf = ShardedBloomFilter(capacity=100, fp_rate=0.01)
        _fill(sf, 0, 10)
        idx = sf.add_shard()
        self.assertEqual(idx, 1)
        head, _cap, _target = sf._shards[-1]
        self.assertEqual(len(head), 0)
        sf.add("fresh")
        self.assertNotIn("fresh", sf._shards[0][0])
        self.assertIn("fresh", sf._shards[1][0])

    def test_new_shard_targets_tighten_geometrically(self):
        sf = ShardedBloomFilter(capacity=100, fp_rate=0.01, tightening=0.5)
        self.assertAlmostEqual(sf._shards[0][2], 0.005)
        sf.add_shard()
        self.assertAlmostEqual(sf._shards[1][2], 0.0025)
        sf.add_shard()
        self.assertAlmostEqual(sf._shards[2][2], 0.00125)

    def test_rejects_bad_args(self):
        with self.assertRaises(ValueError):
            ShardedBloomFilter(capacity=0)
        with self.assertRaises(ValueError):
            ShardedBloomFilter(capacity=100, fp_rate=0.0)
        with self.assertRaises(ValueError):
            ShardedBloomFilter(capacity=100, max_shards=0)
        with self.assertRaises(ValueError):
            ShardedBloomFilter(capacity=100, tightening=1.0)


class TestCrossShardQuery(unittest.TestCase):
    def test_no_false_negatives_across_shards(self):
        sf = ShardedBloomFilter(capacity=100, fp_rate=0.01, max_shards=16)
        words = ["k%d" % i for i in range(500)]
        for w in words:
            sf.add(w)
        self.assertGreater(sf.num_shards, 1)
        for w in words:
            self.assertIn(w, sf)

    def test_every_shard_must_be_checked(self):
        # 新挂一片空片，只往新片写一条；旧片全空，跳过新片必查不到。
        sf = ShardedBloomFilter(capacity=100, fp_rate=0.01)
        sf.add_shard()
        item = "only-in-new-shard"
        sf.add(item)
        for bf, _c, _t in sf._shards[:-1]:
            self.assertNotIn(item, bf)
        self.assertIn(item, sf._shards[-1][0])
        # 问遍所有片才是 True：漏一片，去重当场失效。
        self.assertIn(item, sf)

    def test_home_shard_covers_every_insert(self):
        sf = ShardedBloomFilter(capacity=50, fp_rate=0.001, max_shards=16)
        words = ["shard-item-%d" % i for i in range(200)]
        home = []
        for w in words:
            sf.add(w)
            home.append(sf.num_shards - 1)
        self.assertGreater(sf.num_shards, 1)
        for w, idx in zip(words, home):
            self.assertIn(w, sf._shards[idx][0])
            self.assertIn(w, sf)

    def test_absent_item_reported_absent(self):
        sf = ShardedBloomFilter(capacity=100, fp_rate=0.001)
        _fill(sf, 0, 100)
        self.assertNotIn("never-inserted-xyz", sf)


class TestOverallFpRate(unittest.TestCase):
    def test_empty_and_single_shard(self):
        sf = ShardedBloomFilter(capacity=1000, fp_rate=0.01)
        self.assertEqual(sf.fp_rate, 0.0)
        for i in range(100):
            sf.add("x%d" % i)
        bf = sf._shards[0][0]
        expected = sf._shard_fp(bf)
        self.assertAlmostEqual(sf.fp_rate, expected)

    def test_aggregated_across_all_shards(self):
        sf = ShardedBloomFilter(capacity=100, fp_rate=0.01, max_shards=16)
        _fill(sf, 0, 300)
        expected = 1.0
        for bf, _c, _t in sf._shards:
            n = len(bf)
            p = 0.0 if n == 0 else (
                1.0 - math.exp(-bf.num_hashes * n / bf.num_bits)
            ) ** bf.num_hashes
            expected *= 1.0 - p
        expected = 1.0 - expected
        self.assertAlmostEqual(sf.fp_rate, expected, places=12)

    def test_overall_rate_stays_near_target(self):
        # 2.5 片写满，收紧后的整体假阳性率仍在目标 1% 之内。
        sf = ShardedBloomFilter(capacity=400, fp_rate=0.01, max_shards=16)
        for i in range(1000):
            sf.add("k%d" % i)
        self.assertLess(sf.fp_rate, 0.01)

    def test_empirical_overall_rate_matches_formula(self):
        sf = ShardedBloomFilter(capacity=400, fp_rate=0.01, max_shards=16)
        for i in range(1000):
            sf.add(("k", i))
        trials = 20000
        false_hits = sum(("absent", i) in sf for i in range(trials))
        observed = false_hits / trials
        self.assertLess(observed, 0.02)
        self.assertAlmostEqual(observed, sf.fp_rate, delta=0.004)


class TestLegacyFormat(unittest.TestCase):
    def test_reads_old_single_instance_blob(self):
        old = BloomFilter(capacity=1000, fp_rate=0.01)
        for word in ["alpha", "beta", "gamma"]:
            old.add(word)
        sf = ShardedBloomFilter.from_bytes(old.to_bytes())
        self.assertEqual(sf.num_shards, 1)
        for word in ["alpha", "beta", "gamma"]:
            self.assertIn(word, sf)
        self.assertNotIn("delta", sf)
        self.assertEqual(len(sf), 3)

    def test_legacy_shard_bytes_untouched(self):
        old = BloomFilter(capacity=1000, fp_rate=0.01)
        old.add("alpha")
        blob = old.to_bytes()
        sf = ShardedBloomFilter.from_bytes(blob)
        self.assertEqual(sf._shards[0][0].to_bytes(), blob)

    def test_legacy_capacity_inferred_near_design(self):
        old = BloomFilter(capacity=1000, fp_rate=0.01)
        sf = ShardedBloomFilter.from_bytes(old.to_bytes())
        self.assertGreater(sf.capacity, 900)
        self.assertLess(sf.capacity, 1100)

    def test_legacy_accepts_capacity_override_and_grows(self):
        old = BloomFilter(capacity=1000, fp_rate=0.01)
        old.add("seed")
        sf = ShardedBloomFilter.from_bytes(
            old.to_bytes(), capacity=10, max_shards=8)
        self.assertEqual(sf.capacity, 10)
        for i in range(25):
            sf.add("new%d" % i)
        self.assertGreater(sf.num_shards, 1)
        self.assertIn("seed", sf)

    def test_legacy_saved_as_new_format_after_write(self):
        old = BloomFilter(capacity=100, fp_rate=0.01)
        old.add("alpha")
        sf = ShardedBloomFilter.from_bytes(old.to_bytes(), max_shards=8)
        sf.add("beta")
        self.assertEqual(sf.to_bytes()[:4], MAGIC)
        self.assertNotEqual(MAGIC, LEGACY_MAGIC)
        restored = ShardedBloomFilter.from_bytes(sf.to_bytes())
        self.assertIn("alpha", restored)
        self.assertIn("beta", restored)


class TestPersistence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        for name in os.listdir(self.tmp):
            os.unlink(os.path.join(self.tmp, name))
        os.rmdir(self.tmp)

    def test_roundtrip_restores_every_shard(self):
        sf = ShardedBloomFilter(capacity=100, fp_rate=0.01, max_shards=8)
        words = ["k%d" % i for i in range(250)]
        for w in words:
            sf.add(w)
        path = os.path.join(self.tmp, "state.bin")
        sf.save(path)
        restored = ShardedBloomFilter.load(path)
        self.assertEqual(restored.num_shards, sf.num_shards)
        self.assertEqual(restored.to_bytes(), sf.to_bytes())
        for w in words:
            self.assertIn(w, restored)

    def test_load_legacy_file(self):
        old = BloomFilter(capacity=500, fp_rate=0.02)
        old.add("old")
        path = os.path.join(self.tmp, "legacy.bin")
        with open(path, "wb") as fh:
            fh.write(old.to_bytes())
        restored = ShardedBloomFilter.load(path)
        self.assertIn("old", restored)

    def test_rejects_bad_magic(self):
        with self.assertRaises(ValueError):
            ShardedBloomFilter.from_bytes(b"XXXX" + b"\x00" * 32)


class TestConcurrentAddDuringGrowth(unittest.TestCase):
    def test_no_writes_lost_while_shards_are_added(self):
        sf = ShardedBloomFilter(
            capacity=100, fp_rate=0.01, max_shards=128)
        n_threads = 8
        per_thread = 500
        errors = []
        barrier = threading.Barrier(n_threads)

        def writer(tid):
            try:
                barrier.wait()
                for i in range(per_thread):
                    sf.add(("t", tid, i))
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(t,))
                   for t in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        self.assertEqual(len(sf), n_threads * per_thread)
        for tid in range(n_threads):
            for i in range(per_thread):
                self.assertIn(("t", tid, i), sf)
        self.assertGreater(sf.num_shards, 1)

    def test_concurrent_reads_stay_consistent(self):
        sf = ShardedBloomFilter(capacity=100, fp_rate=0.01, max_shards=128)
        stop = threading.Event()
        bad = []

        def writer():
            i = 0
            while not stop.is_set():
                sf.add(("w", i))
                i += 1

        def reader():
            seen = 0
            while not stop.is_set():
                for i in range(seen):
                    if ("w", i) not in sf:
                        bad.append(i)
                        return
                seen = min(len(sf), seen + 32)

        wt = threading.Thread(target=writer)
        readers = [threading.Thread(target=reader) for _ in range(3)]
        wt.start()
        for r in readers:
            r.start()
        threading.Event().wait(0.5)
        stop.set()
        wt.join()
        for r in readers:
            r.join()
        self.assertEqual(bad, [])


class TestMemoryFallback(unittest.TestCase):
    def test_explicit_add_shard_hits_ceiling(self):
        sf = ShardedBloomFilter(capacity=100, fp_rate=0.01, max_shards=2)
        sf.add_shard()
        with self.assertRaises(ShardFullError):
            sf.add_shard()

    def test_overflow_falls_back_to_last_shard(self):
        sf = ShardedBloomFilter(capacity=50, fp_rate=0.01, max_shards=2)
        words = ["overflow-%d" % i for i in range(300)]
        for w in words:
            sf.add(w)
        self.assertEqual(sf.num_shards, 2)
        self.assertTrue(sf.sealed)
        self.assertEqual(len(sf), 300)
        for w in words:
            self.assertIn(w, sf)

    def test_sealed_survives_roundtrip(self):
        sf = ShardedBloomFilter(capacity=50, fp_rate=0.01, max_shards=2)
        for i in range(120):
            sf.add("k%d" % i)
        self.assertTrue(sf.sealed)
        restored = ShardedBloomFilter.from_bytes(sf.to_bytes())
        self.assertTrue(restored.sealed)
        restored.add("after-restart")
        self.assertEqual(restored.num_shards, 2)
        self.assertIn("after-restart", restored)


if __name__ == "__main__":
    unittest.main()
