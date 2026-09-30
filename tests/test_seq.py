"""朴素列表序列的锁定测试。

只覆盖当前实现已经具备的能力：按位置取值、按位置插入与删除、区间
求和、区间最小最大、区间第 k 小、按排名找元素，以及越界与参数错误
的报错口径。新增能力（无旋树路径、按大小分裂与按优先级合并、两条
路径逐项对照、各项边界）另开测试文件，本文件一字不改。
"""

import unittest

from treap import Erro, Seq
from treap.seq import ArgErro, IndexErro, RangeErro


class TestBuildAndGet(unittest.TestCase):
    def test_len_and_to_list(self):
        seq = Seq([1, 2, 3, 4])
        self.assertEqual(len(seq), 4)
        self.assertEqual(seq.to_list(), [1, 2, 3, 4])

    def test_empty_sequence(self):
        seq = Seq()
        self.assertEqual(len(seq), 0)
        self.assertEqual(seq.to_list(), [])

    def test_to_list_is_a_copy(self):
        seq = Seq([1, 2])
        copy = seq.to_list()
        copy.append(99)
        self.assertEqual(seq.to_list(), [1, 2])

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


class TestInsertDelete(unittest.TestCase):
    def test_insert_at_head_middle_tail(self):
        seq = Seq([1, 2, 3])
        seq.insert(0, 0)
        self.assertEqual(seq.to_list(), [0, 1, 2, 3])
        seq.insert(2, 9)
        self.assertEqual(seq.to_list(), [0, 1, 9, 2, 3])
        seq.insert(5, 7)
        self.assertEqual(seq.to_list(), [0, 1, 9, 2, 3, 7])

    def test_insert_into_empty(self):
        seq = Seq()
        seq.insert(0, 5)
        self.assertEqual(seq.to_list(), [5])
        self.assertEqual(len(seq), 1)

    def test_insert_rejects_bad_position(self):
        seq = Seq([1, 2])
        with self.assertRaises(IndexErro):
            seq.insert(3, 0)
        with self.assertRaises(IndexErro):
            seq.insert(-1, 0)

    def test_insert_rejects_non_int_value(self):
        seq = Seq([1])
        with self.assertRaises(ArgErro):
            seq.insert(0, 1.5)

    def test_remove_returns_value(self):
        seq = Seq([1, 2, 3, 4])
        self.assertEqual(seq.remove(1), 2)
        self.assertEqual(seq.to_list(), [1, 3, 4])
        self.assertEqual(seq.remove(0), 1)
        self.assertEqual(seq.to_list(), [3, 4])

    def test_remove_last(self):
        seq = Seq([1, 2, 3])
        self.assertEqual(seq.remove(2), 3)
        self.assertEqual(seq.to_list(), [1, 2])

    def test_remove_rejects_out_of_range(self):
        seq = Seq([1, 2])
        with self.assertRaises(IndexErro):
            seq.remove(2)
        with self.assertRaises(IndexErro):
            seq.remove(-1)


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


class TestMinMax(unittest.TestCase):
    def test_min_and_max_basic(self):
        seq = Seq([5, 3, 8, 1])
        self.assertEqual(seq.min(0, 4), 1)
        self.assertEqual(seq.max(0, 4), 8)

    def test_min_max_single_element_range(self):
        seq = Seq([4, 9, 2])
        self.assertEqual(seq.min(1, 2), 9)
        self.assertEqual(seq.max(2, 3), 2)

    def test_min_max_empty_range_is_zero(self):
        seq = Seq([4, 9, 2])
        self.assertEqual(seq.min(1, 1), 0)
        self.assertEqual(seq.max(2, 2), 0)

    def test_min_max_all_equal(self):
        seq = Seq([7, 7])
        self.assertEqual(seq.min(0, 2), 7)
        self.assertEqual(seq.max(0, 2), 7)

    def test_min_max_reject_bad_range(self):
        seq = Seq([1, 2, 3])
        with self.assertRaises(RangeErro):
            seq.min(2, 1)
        with self.assertRaises(RangeErro):
            seq.max(0, 4)


class TestKthAndRank(unittest.TestCase):
    def test_kth_from_smallest(self):
        seq = Seq([5, 3, 8, 1, 9, 2])
        self.assertEqual(seq.kth(0, 6, 0), 1)
        self.assertEqual(seq.kth(0, 6, 1), 2)
        self.assertEqual(seq.kth(0, 6, 5), 9)

    def test_kth_on_sub_range(self):
        seq = Seq([5, 3, 8, 1, 9, 2])
        self.assertEqual(seq.kth(1, 4, 0), 1)
        self.assertEqual(seq.kth(1, 4, 2), 8)

    def test_kth_duplicates_take_separate_ranks(self):
        seq = Seq([2, 2, 3, 2])
        self.assertEqual(seq.kth(0, 4, 0), 2)
        self.assertEqual(seq.kth(0, 4, 2), 2)
        self.assertEqual(seq.kth(0, 4, 3), 3)

    def test_kth_rejects_bad_k(self):
        seq = Seq([1, 2, 3])
        with self.assertRaises(RangeErro):
            seq.kth(0, 3, 3)
        with self.assertRaises(RangeErro):
            seq.kth(0, 3, -1)

    def test_rank_counts_strictly_smaller(self):
        seq = Seq([5, 3, 8, 1, 9, 2])
        self.assertEqual(seq.rank(3), 0)
        self.assertEqual(seq.rank(1), 2)
        self.assertEqual(seq.rank(4), 5)

    def test_rank_of_duplicates_is_equal(self):
        seq = Seq([4, 1, 4, 2])
        self.assertEqual(seq.rank(0), seq.rank(2))
        self.assertEqual(seq.rank(0), 2)

    def test_rank_rejects_out_of_range(self):
        seq = Seq([1, 2])
        with self.assertRaises(IndexErro):
            seq.rank(2)


class TestErrorHierarchy(unittest.TestCase):
    def test_errors_share_base(self):
        self.assertTrue(issubclass(IndexErro, Erro))
        self.assertTrue(issubclass(RangeErro, Erro))
        self.assertTrue(issubclass(ArgErro, Erro))

    def test_catching_base_covers_all(self):
        seq = Seq([1])
        with self.assertRaises(Erro):
            seq.get(5)


if __name__ == "__main__":
    unittest.main()
