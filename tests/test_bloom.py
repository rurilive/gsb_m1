"""布隆过滤器新行为的测试：省扫描、压实无假阴、落盘往返、扩容回落。"""

import math
import os
import tempfile
import unittest

from blooms.bloom import BloomFilter
from blooms.table import MemTable


class TestLevelBloomSkips(unittest.TestCase):
    def test_absent_key_skips_every_level(self):
        t = MemTable(level_capacity=1, ratio=2)
        for i, k in enumerate("abcd"):
            t.put(k, i)
        levels = t.levels()
        self.assertEqual(len(levels), 3)
        before = t.stats()
        self.assertIsNone(t.get("zz"))
        after = t.stats()
        # 三层过滤器都说没有，整层全跳过，一次 dict 扫描都不该发生
        self.assertEqual(after["bloom_skips"] - before["bloom_skips"], 3)
        self.assertEqual(after["bloom_scans"] - before["bloom_scans"], 0)
        self.assertEqual(after["bloom_penetrations"] - before["bloom_penetrations"], 0)
        self.assertEqual(after["misses"] - before["misses"], 1)

    def test_present_key_scans_until_hit(self):
        t = MemTable(level_capacity=1, ratio=2)
        for i, k in enumerate("abcd"):
            t.put(k, i)
        before = t.stats()
        self.assertEqual(t.get("a"), 0)
        after = t.stats()
        # L0、L1 过滤器说没有直接跳过，只扫了 L2
        self.assertEqual(after["bloom_skips"] - before["bloom_skips"], 2)
        self.assertEqual(after["bloom_scans"] - before["bloom_scans"], 1)

    def test_hit_in_newest_level_skips_all_deeper(self):
        t = MemTable(level_capacity=2, ratio=4)
        for i, k in enumerate("abc"):
            t.put(k, i)
        t.put("fresh", 9)
        before = t.stats()
        self.assertEqual(t.get("fresh"), 9)
        after = t.stats()
        # 第一层就命中，后面的层压根不访问：无跳过也无额外扫描
        self.assertEqual(after["bloom_skips"] - before["bloom_skips"], 0)
        self.assertEqual(after["bloom_scans"] - before["bloom_scans"], 1)

    def test_stats_include_per_level_rates(self):
        t = MemTable(level_capacity=1, ratio=2, error_rate=0.05)
        for i, k in enumerate("abcd"):
            t.put(k, i)
        s = t.stats()
        self.assertEqual(len(s["bloom_level_error_rates"]), s["levels"])
        self.assertEqual(s["bloom_level_error_rates"][0], 0.0)
        self.assertLessEqual(s["bloom_estimated_error_rate"], 0.05)


class TestRebuildAfterCompaction(unittest.TestCase):
    def test_no_false_negative_after_single_compaction(self):
        t = MemTable(level_capacity=2, ratio=4)
        for i, k in enumerate("abc"):
            t.put(k, i)
        levels = t.levels()
        self.assertEqual(levels[0], {})
        for i, k in enumerate("abc"):
            self.assertEqual(t.get(k), i)

    def test_no_false_negative_through_repeated_compactions(self):
        t = MemTable(level_capacity=1, ratio=2)
        keys = [f"k{i}" for i in range(20)]
        for i, k in enumerate(keys):
            t.put(k, i)
            # 每写一个都查一遍所有已写键，任何一层重建漏掉都会当场暴露
            for j in range(i + 1):
                self.assertEqual(t.get(keys[j]), j)

    def test_overwritten_key_still_reachable_after_cascade(self):
        t = MemTable(level_capacity=1, ratio=2)
        for i, k in enumerate("abcd"):
            t.put(k, i)
        t.put("a", 99)
        t.put("a", 100)
        for offset, k in enumerate("bcd"):
            t.put(k, 10 + offset)
        self.assertEqual(t.get("a"), 100)
        self.assertEqual(t.get("b"), 10)
        self.assertEqual(t.get("c"), 11)
        self.assertEqual(t.get("d"), 12)


class TestBloomGrowth(unittest.TestCase):
    def test_error_rate_comes_back_down_after_growth(self):
        flt = BloomFilter(100, 0.01)
        for i in range(100):
            flt.add(f"k{i}")
        at_capacity = flt.estimated_false_positive_rate()
        self.assertLessEqual(at_capacity, 0.01)
        for i in range(100, 300):
            flt.add(f"k{i}")
        # 写穿建时容量触发了扩容
        self.assertGreater(flt.expected_items, 100)
        self.assertGreater(flt.num_bits, 1000)
        after_growth = flt.estimated_false_positive_rate()
        self.assertLessEqual(after_growth, 0.01)
        # 实测假阳率也回落到目标附近，而不是一路飘高
        false_positives = sum(
            1 for i in range(20000) if flt.might_contain(f"absent-{i}")
        )
        self.assertLess(false_positives / 20000, 0.02)
        for i in range(300):
            self.assertTrue(flt.might_contain(f"k{i}"))

    def test_without_growth_rate_would_saturate(self):
        # 对照组：固定建时容量与位数组，写多了误判率必然逼近 1
        n, p = 100, 0.01
        m = math.ceil(-n * math.log(p) / math.log(2) ** 2)
        k = max(1, round(m / n * math.log(2)))
        overfilled = 10 * n
        saturated = (1 - math.exp(-k * overfilled / m)) ** k
        self.assertGreater(saturated, 0.9)

    def test_growth_keeps_all_keys_members(self):
        flt = BloomFilter(10, 0.01)
        for i in range(500):
            flt.add(i)
        for i in range(500):
            self.assertTrue(flt.might_contain(i))


class TestSerialization(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        for name in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, name))
        os.rmdir(self.tmpdir)

    def test_bloom_filter_roundtrip(self):
        flt = BloomFilter(50, 0.02)
        for i in range(120):
            flt.add(f"key-{i}")
        path = os.path.join(self.tmpdir, "f.blm")
        flt.dump(path)
        restored = BloomFilter.load(path)
        self.assertEqual(restored.expected_items, flt.expected_items)
        self.assertEqual(restored.error_rate, flt.error_rate)
        self.assertEqual(restored.num_bits, flt.num_bits)
        self.assertEqual(restored.num_hashes, flt.num_hashes)
        self.assertEqual(len(restored), len(flt))
        self.assertEqual(
            restored.estimated_false_positive_rate(),
            flt.estimated_false_positive_rate(),
        )
        for i in range(120):
            self.assertTrue(restored.might_contain(f"key-{i}"))
        self.assertFalse(restored.might_contain("definitely-absent"))

    def test_table_roundtrip_behaviour_and_stats(self):
        t = MemTable(level_capacity=1, ratio=2, error_rate=0.02)
        for i, k in enumerate("abcdefgh"):
            t.put(k, i)
        t.get("a")
        t.get("zz")
        path = os.path.join(self.tmpdir, "t.blm")
        t.dump(path)
        restored = MemTable.load(path)
        self.assertEqual(restored.levels(), t.levels())
        self.assertEqual(restored.stats(), t.stats())
        for i, k in enumerate("abcdefgh"):
            self.assertEqual(restored.get(k), t.get(k))
        self.assertIsNone(restored.get("yy"))
        # 读回后继续压实也不能出假阴
        for i in range(8, 16):
            restored.put(f"n{i}", i)
        for i in range(16):
            key = "abcdefgh"[i] if i < 8 else f"n{i}"
            self.assertEqual(restored.get(key), i)

    def test_table_roundtrip_params_preserved(self):
        t = MemTable(level_capacity=3, ratio=5, error_rate=0.001)
        for i in range(7):
            t.put(f"k{i}", i)
        path = os.path.join(self.tmpdir, "t2.blm")
        t.dump(path)
        restored = MemTable.load(path)
        self.assertEqual(restored._level_capacity, 3)
        self.assertEqual(restored._ratio, 5)
        self.assertEqual(restored._error_rate, 0.001)
        for flt in restored._filters:
            self.assertEqual(flt.error_rate, 0.001)

    def test_load_rejects_bad_magic(self):
        path = os.path.join(self.tmpdir, "bad.blm")
        with open(path, "wb") as handle:
            handle.write(b"nope" * 4)
        with self.assertRaises(ValueError):
            BloomFilter.load(path)
        with self.assertRaises(ValueError):
            MemTable.load(path)


class TestBloomParameters(unittest.TestCase):
    def test_invalid_error_rate_rejected(self):
        with self.assertRaises(ValueError):
            BloomFilter(10, 0)
        with self.assertRaises(ValueError):
            BloomFilter(10, 1)
        with self.assertRaises(ValueError):
            MemTable(error_rate=0)
        with self.assertRaises(ValueError):
            MemTable(error_rate=1.5)

    def test_invalid_expected_items_rejected(self):
        with self.assertRaises(ValueError):
            BloomFilter(0, 0.01)


if __name__ == "__main__":
    unittest.main()
