"""布隆过滤器新行为测试。"""

import unittest

from blooms.bloom import BloomFilter


class TestBloomFilter(unittest.TestCase):
    def test_no_false_negatives_basic(self):
        f = BloomFilter(100, error_rate=0.01)
        for i in range(100):
            f.add(f"k{i}")
        for i in range(100):
            self.assertIn(f"k{i}", f)

    def test_invalid_error_rate_raises(self):
        for bad in (0.0, 1.0, -0.1, 2.0):
            with self.assertRaises(ValueError):
                BloomFilter(100, error_rate=bad)

    def test_invalid_expected_items_raises(self):
        with self.assertRaises(ValueError):
            BloomFilter(0)

    def test_saturated_then_rebuild_growth_brings_fpp_down(self):
        # 建时只给 20 条容量，实际塞 800 条：写超后误判率一路飘
        f = BloomFilter(20, error_rate=0.02)
        for i in range(800):
            f.add(i)
        self.assertTrue(f.saturated)
        blown_fpp = f.estimated_false_positive_rate
        self.assertGreater(blown_fpp, 0.5)

        # 按当前键集扩容重建，误判率必须回落到目标附近
        f.rebuild(range(800))
        self.assertFalse(f.saturated)
        self.assertLess(f.estimated_false_positive_rate, 0.05)
        for i in range(800):
            self.assertIn(i, f)

        # 实测误判率也得回落，而不只是公式好看
        false_positives = sum(1 for i in range(800, 8800) if f.might_contain(i))
        self.assertLess(false_positives / 8000, 0.05)

    def test_rebuild_with_changed_keyset_has_no_false_negative(self):
        f = BloomFilter(10, error_rate=0.01)
        for i in range(10):
            f.add(f"old{i}")
        # 压实式键集变更：全量换成新键，重建后新键一个不能漏
        f.rebuild([f"new{i}" for i in range(10)])
        for i in range(10):
            self.assertIn(f"new{i}", f)

    def test_to_dict_round_trip(self):
        f = BloomFilter(50, error_rate=0.03)
        for i in range(50):
            f.add(f"k{i}")
        restored = BloomFilter.from_dict(f.to_dict())
        self.assertEqual(restored.expected_items, 50)
        self.assertEqual(restored.error_rate, 0.03)
        self.assertEqual(restored.items, 50)
        for i in range(50):
            self.assertIn(f"k{i}", restored)
        self.assertAlmostEqual(
            restored.estimated_false_positive_rate,
            f.estimated_false_positive_rate,
        )

    def test_from_dict_rejects_tampered_parameters(self):
        f = BloomFilter(50, error_rate=0.03)
        image = f.to_dict()
        image["error_rate"] = 0.5
        with self.assertRaises(ValueError):
            BloomFilter.from_dict(image)


if __name__ == "__main__":
    unittest.main()
