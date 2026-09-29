"""基线测试：锁定 beatsx.seg.NaiveSeg 的现状行为。

这些用例把「逐项处理」的现有事实固定下来，任何改造都必须让它们继续全绿。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from beatsx.seg import BeatsError, NaiveSeg


class InitTest(unittest.TestCase):
    def test_构造拷贝输入(self):
        src = [3, 1, 4, 1, 5]
        seg = NaiveSeg(src)
        src[0] = 999
        self.assertEqual(seg.to_list(), [3, 1, 4, 1, 5])
        self.assertEqual(seg.n, 5)

    def test_空数组(self):
        seg = NaiveSeg([])
        self.assertEqual(seg.n, 0)
        self.assertEqual(seg.to_list(), [])

    def test_非整数元素报错(self):
        with self.assertRaises(BeatsError):
            NaiveSeg([1, "2", 3])
        with self.assertRaises(BeatsError):
            NaiveSeg([1, 2.5])
        with self.assertRaises(BeatsError):
            NaiveSeg([1, True])


class AccessTest(unittest.TestCase):
    def setUp(self):
        self.seg = NaiveSeg([3, 1, 4, 1, 5, 9, 2, 6])

    def test_get取值(self):
        self.assertEqual(self.seg.get(0), 3)
        self.assertEqual(self.seg.get(7), 6)

    def test_get越界报错(self):
        with self.assertRaises(BeatsError):
            self.seg.get(8)
        with self.assertRaises(BeatsError):
            self.seg.get(-1)

    def test_get非整数下标报错(self):
        with self.assertRaises(BeatsError):
            self.seg.get(1.5)


class RangeSumTest(unittest.TestCase):
    def setUp(self):
        self.seg = NaiveSeg([3, 1, 4, 1, 5, 9, 2, 6])

    def test_整段求和(self):
        self.assertEqual(self.seg.range_sum(0, 8), 31)

    def test_子区间求和(self):
        self.assertEqual(self.seg.range_sum(2, 5), 10)
        self.assertEqual(self.seg.range_sum(0, 1), 3)

    def test_空区间返回零(self):
        self.assertEqual(self.seg.range_sum(3, 3), 0)
        self.assertEqual(self.seg.range_sum(0, 0), 0)
        self.assertEqual(NaiveSeg([]).range_sum(0, 0), 0)


class RangeMaxMinTest(unittest.TestCase):
    def setUp(self):
        self.seg = NaiveSeg([3, 1, 4, 1, 5, 9, 2, 6])

    def test_区间最大(self):
        self.assertEqual(self.seg.range_max(0, 8), 9)
        self.assertEqual(self.seg.range_max(0, 4), 4)
        self.assertEqual(self.seg.range_max(6, 8), 6)

    def test_区间最小(self):
        self.assertEqual(self.seg.range_min(0, 8), 1)
        self.assertEqual(self.seg.range_min(2, 6), 1)
        self.assertEqual(self.seg.range_min(7, 8), 6)

    def test_空区间返回None(self):
        self.assertIsNone(self.seg.range_max(4, 4))
        self.assertIsNone(self.seg.range_min(4, 4))


class ChminChmaxTest(unittest.TestCase):
    def test_chmin逐项改写(self):
        seg = NaiveSeg([3, 1, 4, 1, 5, 9, 2, 6])
        seg.chmin(1, 6, 4)
        self.assertEqual(seg.to_list(), [3, 1, 4, 1, 4, 4, 2, 6])

    def test_chmax逐项改写(self):
        seg = NaiveSeg([3, 1, 4, 1, 5, 9, 2, 6])
        seg.chmax(0, 3, 3)
        self.assertEqual(seg.to_list(), [3, 3, 4, 1, 5, 9, 2, 6])

    def test_chmin值大于全部元素时无改动(self):
        seg = NaiveSeg([3, 1, 4])
        seg.chmin(0, 3, 100)
        self.assertEqual(seg.to_list(), [3, 1, 4])

    def test_chmax值小于全部元素时无改动(self):
        seg = NaiveSeg([3, 1, 4])
        seg.chmax(0, 3, -100)
        self.assertEqual(seg.to_list(), [3, 1, 4])

    def test_空区间取最值无改动(self):
        seg = NaiveSeg([3, 1, 4])
        seg.chmin(2, 2, 0)
        seg.chmax(2, 2, 9)
        self.assertEqual(seg.to_list(), [3, 1, 4])

    def test_取最值后可继续查询(self):
        seg = NaiveSeg([3, 1, 4, 1, 5, 9, 2, 6])
        seg.chmin(0, 8, 5)
        self.assertEqual(seg.range_sum(0, 8), 26)
        seg.chmax(0, 8, 3)
        self.assertEqual(seg.range_max(0, 8), 5)
        self.assertEqual(seg.range_min(0, 8), 3)


class IllegalRangeTest(unittest.TestCase):
    def setUp(self):
        self.seg = NaiveSeg([3, 1, 4, 1, 5])

    def test_左大于右报错(self):
        for fn in (self.seg.range_sum, self.seg.range_max, self.seg.range_min):
            with self.assertRaises(BeatsError):
                fn(3, 2)

    def test_越界报错(self):
        with self.assertRaises(BeatsError):
            self.seg.range_sum(0, 6)
        with self.assertRaises(BeatsError):
            self.seg.range_sum(-1, 3)
        with self.assertRaises(BeatsError):
            self.seg.chmin(0, 6, 1)
        with self.assertRaises(BeatsError):
            self.seg.chmax(-1, 3, 1)

    def test_非整数端点报错(self):
        with self.assertRaises(BeatsError):
            self.seg.range_sum(0.0, 3)
        with self.assertRaises(BeatsError):
            self.seg.range_max(0, "3")
        with self.assertRaises(BeatsError):
            self.seg.chmin(0, 3, 2.0)


class ErrorHierarchyTest(unittest.TestCase):
    def test_异常继承基类(self):
        self.assertTrue(issubclass(BeatsError, Exception))
        seg = NaiveSeg([1, 2, 3])
        with self.assertRaises(BeatsError):
            seg.range_sum(5, 1)


if __name__ == "__main__":
    unittest.main()
