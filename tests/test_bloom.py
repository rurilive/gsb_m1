"""NaiveBloomFilter 现有行为的锁定测试，改造后仍须全绿。"""

import unittest

from bloomchain import NaiveBloomFilter
from bloomchain.naive import NaiveBloomFilter as NaiveBloomDirect


class TestNaiveBloomFilter(unittest.TestCase):
    def test_added_keys_always_hit(self):
        bf = NaiveBloomFilter(capacity=100)
        keys = ["u%d" % i for i in range(100)]
        for k in keys:
            bf.add(k)
        for k in keys:
            self.assertIn(k, bf)

    def test_missing_keys_mostly_miss(self):
        bf = NaiveBloomFilter(capacity=50, fp_rate=0.01)
        for i in range(50):
            bf.add("in-%d" % i)
        misses = sum(1 for i in range(500) if ("out-%d" % i) not in bf)
        self.assertGreater(misses, 400)

    def test_contains_method_matches_in(self):
        bf = NaiveBloomFilter(capacity=16)
        bf.add("x")
        self.assertEqual(bf.contains("x"), "x" in bf)

    def test_empty_filter_misses_everything(self):
        bf = NaiveBloomFilter(capacity=16)
        for i in range(50):
            self.assertNotIn("n-%d" % i, bf)

    def test_len_counts_adds(self):
        bf = NaiveBloomFilter(capacity=10)
        bf.add("a")
        bf.add("a")
        self.assertEqual(len(bf), 2)

    def test_stats_is_fresh_dict(self):
        bf = NaiveBloomFilter(capacity=8)
        snap = bf.stats()
        snap["added"] = 99
        self.assertEqual(bf.stats()["added"], 0)
        self.assertEqual(bf.stats()["capacity"], 8)

    def test_bad_capacity_rejected(self):
        with self.assertRaises(ValueError):
            NaiveBloomFilter(capacity=0)
        with self.assertRaises(ValueError):
            NaiveBloomFilter(capacity=-5)

    def test_bad_fp_rate_rejected(self):
        with self.assertRaises(ValueError):
            NaiveBloomFilter(capacity=16, fp_rate=0.0)
        with self.assertRaises(ValueError):
            NaiveBloomFilter(capacity=16, fp_rate=1.0)
        with self.assertRaises(ValueError):
            NaiveBloomFilter(capacity=16, fp_rate=1.5)

    def test_exported_name_is_same_class(self):
        self.assertIs(NaiveBloomFilter, NaiveBloomDirect)


if __name__ == "__main__":
    unittest.main()