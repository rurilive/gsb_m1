"""ScalableBloomFilter 行为基线：在线添片、跨片查询、整体假阳性率、旧格式兼容与并发写。"""
import threading
import unittest

from bloomx import BloomFilter, ScalableBloomFilter
from bloomx.shard import MAGIC as SHARD_MAGIC


class TestGrowth(unittest.TestCase):
    def test_grows_online_when_shard_fills(self):
        sbf = ScalableBloomFilter(initial_capacity=100, fp_rate=0.01)
        self.assertEqual(sbf.shard_count, 1)
        first_words = ["w%d" % i for i in range(100)]
        for w in first_words:
            sbf.add(w)
        self.assertEqual(sbf.shard_count, 1)
        for i in range(250):
            sbf.add("x%d" % i)
        self.assertGreater(sbf.shard_count, 1)
        for w in first_words:
            self.assertIn(w, sbf)

    def test_old_shard_is_left_untouched(self):
        sbf = ScalableBloomFilter(initial_capacity=50, fp_rate=0.01)
        for i in range(50):
            sbf.add("a%d" % i)
        first_blob = sbf._shards[0].bf.to_bytes()
        for i in range(200):
            sbf.add("b%d" % i)
        self.assertGreater(sbf.shard_count, 1)
        self.assertEqual(sbf._shards[0].bf.to_bytes(), first_blob)

    def test_max_shards_caps_memory(self):
        sbf = ScalableBloomFilter(initial_capacity=50, fp_rate=0.01, max_shards=1)
        for i in range(50):
            sbf.add(i)
        with self.assertRaises(OverflowError):
            sbf.add("one-too-many")

    def test_rejects_bad_args(self):
        with self.assertRaises(ValueError):
            ScalableBloomFilter(initial_capacity=0)
        with self.assertRaises(ValueError):
            ScalableBloomFilter(fp_rate=1.0)
        with self.assertRaises(ValueError):
            ScalableBloomFilter(ratio=1.0)
        with self.assertRaises(ValueError):
            ScalableBloomFilter(max_shards=0)


class TestCrossShardQuery(unittest.TestCase):
    def test_no_false_negatives_across_shards(self):
        sbf = ScalableBloomFilter(initial_capacity=100, fp_rate=0.01)
        words = ["k%d" % i for i in range(1000)]
        for w in words:
            sbf.add(w)
        self.assertGreater(sbf.shard_count, 1)
        for w in words:
            self.assertIn(w, sbf)
        self.assertEqual(len(sbf), 1000)

    def test_absent_item_is_reported_absent(self):
        sbf = ScalableBloomFilter(initial_capacity=100, fp_rate=0.01)
        for i in range(500):
            sbf.add("present-%d" % i)
        self.assertNotIn("definitely-absent", sbf)


class TestOverallFpRate(unittest.TestCase):
    def test_overall_fp_rate_stays_under_target(self):
        sbf = ScalableBloomFilter(initial_capacity=1000, fp_rate=0.01)
        for i in range(5000):
            sbf.add("k%d" % i)
        self.assertGreater(sbf.shard_count, 1)
        self.assertLessEqual(sbf.overall_fp_rate, 0.01 + 1e-9)

    def test_measured_fp_matches_overall_number(self):
        sbf = ScalableBloomFilter(initial_capacity=1000, fp_rate=0.01)
        for i in range(5000):
            sbf.add("k%d" % i)
        probes = 20000
        hits = sum(1 for i in range(probes) if "probe-%d" % i in sbf)
        self.assertLess(hits / probes, 0.03)


class TestSerialization(unittest.TestCase):
    def _build(self):
        sbf = ScalableBloomFilter(initial_capacity=100, fp_rate=0.01)
        for i in range(400):
            sbf.add("k%d" % i)
        return sbf

    def test_roundtrip_preserves_membership(self):
        sbf = self._build()
        restored = ScalableBloomFilter.from_bytes(sbf.to_bytes())
        self.assertEqual(restored.shard_count, sbf.shard_count)
        self.assertEqual(len(restored), len(sbf))
        for i in range(400):
            self.assertIn("k%d" % i, restored)
        self.assertNotIn("absent", restored)

    def test_roundtrip_is_byte_stable(self):
        sbf = self._build()
        self.assertEqual(sbf.to_bytes(),
                         ScalableBloomFilter.from_bytes(sbf.to_bytes()).to_bytes())

    def test_blob_starts_with_shard_magic(self):
        sbf = ScalableBloomFilter(initial_capacity=100, fp_rate=0.01)
        self.assertTrue(sbf.to_bytes().startswith(SHARD_MAGIC))

    def test_from_bytes_rejects_bad_magic(self):
        sbf = ScalableBloomFilter(initial_capacity=100, fp_rate=0.01)
        blob = b"XXXX" + sbf.to_bytes()[4:]
        with self.assertRaises(ValueError):
            ScalableBloomFilter.from_bytes(blob)

    def test_from_bytes_rejects_truncated_blob(self):
        sbf = self._build()
        with self.assertRaises(ValueError):
            ScalableBloomFilter.from_bytes(b"BL")
        with self.assertRaises(ValueError):
            ScalableBloomFilter.from_bytes(sbf.to_bytes()[:20])

    def test_can_grow_after_reload(self):
        sbf = self._build()
        restored = ScalableBloomFilter.from_bytes(sbf.to_bytes())
        for i in range(2000):
            restored.add("post-restart-%d" % i)
        for i in range(2000):
            self.assertIn("post-restart-%d" % i, restored)


class TestLegacyFormat(unittest.TestCase):
    def test_reads_legacy_single_instance_blob(self):
        bf = BloomFilter(capacity=500, fp_rate=0.01)
        words = ["legacy-%d" % i for i in range(300)]
        for w in words:
            bf.add(w)
        sbf = ScalableBloomFilter.from_bytes(bf.to_bytes())
        self.assertEqual(sbf.shard_count, 1)
        for w in words:
            self.assertIn(w, sbf)
        self.assertNotIn("never-written", sbf)

    def test_grows_on_top_of_legacy_shard(self):
        bf = BloomFilter(capacity=100, fp_rate=0.01)
        for i in range(100):
            bf.add("old-%d" % i)
        sbf = ScalableBloomFilter.from_bytes(bf.to_bytes())
        for i in range(500):
            sbf.add("new-%d" % i)
        self.assertGreater(sbf.shard_count, 1)
        for i in range(100):
            self.assertIn("old-%d" % i, sbf)
        for i in range(500):
            self.assertIn("new-%d" % i, sbf)


class TestConcurrentWrites(unittest.TestCase):
    def test_no_write_lost_while_growing(self):
        sbf = ScalableBloomFilter(initial_capacity=200, fp_rate=0.01)
        threads_n, per_thread = 4, 500

        def writer(base):
            for i in range(base, base + per_thread):
                sbf.add("item-%d" % i)

        threads = [threading.Thread(target=writer, args=(t * per_thread,))
                   for t in range(threads_n)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        self.assertGreater(sbf.shard_count, 1)
        self.assertEqual(len(sbf), threads_n * per_thread)
        for i in range(threads_n * per_thread):
            self.assertIn("item-%d" % i, sbf)


if __name__ == "__main__":
    unittest.main()
