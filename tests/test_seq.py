"""朴素列表序列的锁定测试。

只覆盖当前实现已经具备的能力：按位置取值、区间翻转、区间求和、
区间赋值、区间最小最大，以及越界与参数错误的报错口径。新增能力
（伸展树路径、按需把节点旋到根、两条路径逐项对照、各项边界）另开
测试文件，本文件一字不改。
"""

import unittest

from splay import Erro, Seq
from splay.seq import ArgErro, IndexErro, RangeErro


class TestBuildAndGet(unittest.TestCase):
    def test_len_and_to_list(self):
        seq = Seq([1, 2, 3, 4])
        self.assertEqual(len(seq), 4)
        self.assertEqual(seq.to_list(), [1, 2, 3, 4])

    def test_empty_sequence(self):
        seq = Seq()
        self.assertEqual(len(seq), 0)
        self.assertEqual(seq.to_list(), [])

    def test_get_first_middle_last(self):
        seq = Seq([10, 20, 30])
        self.assertEqual(seq.get(0), 10)
        self.assertEqual(seq.get(1), 20)
        self.assertEqual(seq.get(2), 30)

    def test_get_rejects_out_of_range(self):
        seq = Seq([1, 2])
        with self.assertRaises(IndexErro):
            seq.get(2)
        with self.assertRaises(IndexErro):
            seq.get(-1)

    def test_get_rejects_non_int(self):
        seq = Seq([1])
        with self.assertRaises(ArgErro):
            seq.get(0.5)
        with self.assertRaises(ArgErro):
            seq.get("0")


class TestReverse(unittest.TestCase):
    def test_reverse_middle(self):
        seq = Seq([1, 2, 3, 4, 5])
        seq.reverse(1, 4)
        self.assertEqual(seq.to_list(), [1, 4, 3, 2, 5])

    def test_reverse_whole(self):
        seq = Seq([1, 2, 3])
        seq.reverse(0, 3)
        self.assertEqual(seq.to_list(), [3, 2, 1])

    def test_reverse_single_and_empty_range_noop(self):
        seq = Seq([1, 2, 3])
        seq.reverse(1, 2)
        self.assertEqual(seq.to_list(), [1, 2, 3])
        seq.reverse(1, 1)
        self.assertEqual(seq.to_list(), [1, 2, 3])

    def test_reverse_twice_restores(self):
        seq = Seq([1, 2, 3, 4])
        seq.reverse(0, 4)
        seq.reverse(0, 4)
        self.assertEqual(seq.to_list(), [1, 2, 3, 4])

    def test_reverse_rejects_bad_range(self):
        seq = Seq([1, 2, 3])
        with self.assertRaises(RangeErro):
            seq.reverse(2, 1)
        with self.assertRaises(RangeErro):
            seq.reverse(0, 4)
        with self.assertRaises(RangeErro):
            seq.reverse(-1, 2)


class TestSum(unittest.TestCase):
    def test_sum_middle(self):
        seq = Seq([1, 2, 3, 4, 5])
        self.assertEqual(seq.sum(1, 4), 9)

    def test_sum_empty_range_is_zero(self):
        seq = Seq([1, 2, 3])
        self.assertEqual(seq.sum(1, 1), 0)
        self.assertEqual(seq.sum(0, 0), 0)

    def test_sum_all(self):
        seq = Seq([1, 2, 3])
        self.assertEqual(seq.sum(0, 3), 6)

    def test_sum_negative_values(self):
        seq = Seq([-3, 5, -2, 4])
        self.assertEqual(seq.sum(0, 4), 4)

    def test_sum_rejects_bad_range(self):
        seq = Seq([1, 2, 3])
        with self.assertRaises(RangeErro):
            seq.sum(1, 0)
        with self.assertRaises(RangeErro):
            seq.sum(0, 5)


class TestAssign(unittest.TestCase):
    def test_assign_sets_each_position(self):
        seq = Seq([1, 2, 3, 4, 5])
        seq.assign(1, 4, 0)
        self.assertEqual(seq.to_list(), [1, 0, 0, 0, 5])

    def test_assign_single_position(self):
        seq = Seq([1, 2, 3])
        seq.assign(1, 2, 9)
        self.assertEqual(seq.to_list(), [1, 9, 3])

    def test_assign_empty_range_noop(self):
        seq = Seq([1, 2, 3])
        seq.assign(2, 2, 7)
        self.assertEqual(seq.to_list(), [1, 2, 3])

    def test_assign_negative_value(self):
        seq = Seq([0, 0])
        seq.assign(0, 2, -5)
        self.assertEqual(seq.to_list(), [-5, -5])


class TestMinMax(unittest.TestCase):
    def test_min_and_max_basic(self):
        seq = Seq([5, 3, 8, 1])
        self.assertEqual(seq.min(0, 4), 1)
        self.assertEqual(seq.max(0, 4), 8)

    def test_min_max_single_element_range(self):
        seq = Seq([4, 9, 2])
        self.assertEqual(seq.min(1, 2), 9)
        self.assertEqual(seq.max(2, 3), 2)

    def test_min_max_all_equal(self):
        seq = Seq([7, 7])
        self.assertEqual(seq.min(0, 2), 7)
        self.assertEqual(seq.max(0, 2), 7)

    def test_min_max_negative_values(self):
        seq = Seq([-5, -1, -9])
        self.assertEqual(seq.min(0, 3), -9)
        self.assertEqual(seq.max(0, 3), -1)

    def test_min_max_reject_bad_range(self):
        seq = Seq([1, 2, 3])
        with self.assertRaises(RangeErro):
            seq.min(2, 1)
        with self.assertRaises(RangeErro):
            seq.max(0, 4)


class TestErrorHierarchy(unittest.TestCase):
    def test_errors_share_base(self):
        self.assertTrue(issubclass(IndexErro, Erro))
        self.assertTrue(issubclass(RangeErro, Erro))
        self.assertTrue(issubclass(ArgErro, Erro))


if __name__ == "__main__":
    unittest.main()
