"""resvoir 现有行为的锁定测试（基线，一字不改且必须全绿）。

只覆盖当前实现已经具备的能力：全量保留、权重与标签入册、累计流入计数、
样本等于全体、权重求和、全量加权均值、全量分位、按标签分组、清空与
内存无界标记。新增能力（固定容量蓄水池、均匀与加权抽样、分层、样本统计
与误差、样本合并、内存有界）另建测试文件 test_reservoir，不改动本文件。
"""

import unittest

from resvoir.buffer import KeepAll


def build():
    c = KeepAll()
    c.add(10, 1, "a")
    c.add(20, 2, "b")
    c.add(30, 1, "a")
    c.add(40, 2, "b")
    c.add(50, 1, None)
    return c


class TestAddAndShape(unittest.TestCase):
    def test_add_returns_item(self):
        c = KeepAll()
        self.assertEqual(c.add(7), 7)

    def test_add_rejects_non_positive_weight(self):
        c = KeepAll()
        with self.assertRaises(ValueError):
            c.add(1, 0)
        with self.assertRaises(ValueError):
            c.add(1, -3)

    def test_add_rejects_non_number_weight(self):
        c = KeepAll()
        with self.assertRaises(ValueError):
            c.add(1, "2")
        with self.assertRaises(ValueError):
            c.add(1, True)

    def test_accepts_float_weight(self):
        c = KeepAll()
        c.add(1, 2.5)
        self.assertEqual(c.weights(), (2.5,))

    def test_seen_counts_every_add(self):
        c = build()
        self.assertEqual(c.seen(), 5)

    def test_len_is_kept_count(self):
        c = build()
        self.assertEqual(len(c), 5)

    def test_items_insertion_order(self):
        c = build()
        self.assertEqual(c.items(), (10, 20, 30, 40, 50))

    def test_items_returns_tuple(self):
        c = build()
        self.assertIsInstance(c.items(), tuple)

    def test_weights_insertion_order(self):
        c = build()
        self.assertEqual(c.weights(), (1, 2, 1, 2, 1))

    def test_iter_yields_items(self):
        c = build()
        self.assertEqual(list(c), [10, 20, 30, 40, 50])


class TestSampleAndStats(unittest.TestCase):
    def test_sample_is_all_elements(self):
        c = build()
        self.assertEqual(c.sample(), c.items())

    def test_sample_returns_tuple(self):
        c = build()
        self.assertIsInstance(c.sample(), tuple)

    def test_total_weight(self):
        c = build()
        self.assertEqual(c.total_weight(), 7)

    def test_weighted_mean(self):
        c = build()
        self.assertEqual(c.mean(), 30.0)

    def test_mean_of_empty_is_none(self):
        c = KeepAll()
        self.assertIsNone(c.mean())

    def test_quantile_endpoints(self):
        c = build()
        self.assertEqual(c.quantile(0.0), 10)
        self.assertEqual(c.quantile(1.0), 50)

    def test_quantile_midpoint(self):
        c = build()
        self.assertEqual(c.quantile(0.5), 30)

    def test_quantile_interpolates(self):
        c = build()
        self.assertAlmostEqual(c.quantile(0.1), 14.0)

    def test_quantile_single_element(self):
        c = KeepAll()
        c.add(9)
        self.assertEqual(c.quantile(0.7), 9)

    def test_quantile_rejects_out_of_range(self):
        c = build()
        with self.assertRaises(ValueError):
            c.quantile(-0.1)
        with self.assertRaises(ValueError):
            c.quantile(1.5)

    def test_quantile_rejects_non_number(self):
        c = build()
        with self.assertRaises(ValueError):
            c.quantile("half")

    def test_quantile_of_empty_rejected(self):
        c = KeepAll()
        with self.assertRaises(ValueError):
            c.quantile(0.5)

    def test_by_label_groups(self):
        c = build()
        self.assertEqual(c.by_label(), {"a": (10, 30), "b": (20, 40), None: (50,)})


class TestResetAndFlag(unittest.TestCase):
    def test_clear_resets_everything(self):
        c = build()
        c.clear()
        self.assertEqual(len(c), 0)
        self.assertEqual(c.seen(), 0)
        self.assertEqual(c.items(), ())
        self.assertIsNone(c.mean())

    def test_is_bounded_is_false(self):
        c = build()
        self.assertFalse(c.is_bounded())


if __name__ == "__main__":
    unittest.main()
