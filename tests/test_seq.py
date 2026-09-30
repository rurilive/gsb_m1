"""Seq 现有朴素行为的锁定测试。

这些用例把基线的对外行为钉住：构造与规范、按下标取改、按下标增删、
区间翻转、区间加、区间求和与最值、边界与异常层级、操作序列的确定性。
改造时本文件一个字都不许改，新行为一律另开测试文件。
"""

import unittest

from seqx.seq import (
    EmptySequenceError,
    IndexOutOfRangeError,
    InvalidRangeError,
    Seq,
    SeqError,
    ValueRangeError,
    replay,
)


class TestConstruction(unittest.TestCase):
    def test_default_is_empty(self):
        seq = Seq()
        self.assertEqual(len(seq), 0)
        self.assertTrue(seq.is_empty())
        self.assertEqual(seq.to_list(), [])

    def test_from_list(self):
        seq = Seq([1, 2, 3])
        self.assertEqual(len(seq), 3)
        self.assertFalse(seq.is_empty())
        self.assertEqual(seq.to_list(), [1, 2, 3])

    def test_negative_elements_kept(self):
        self.assertEqual(Seq([-1, 0, -3]).to_list(), [-1, 0, -3])

    def test_to_list_returns_copy(self):
        seq = Seq([1, 2, 3])
        got = seq.to_list()
        got.append(99)
        self.assertEqual(seq.to_list(), [1, 2, 3])

    def test_non_integer_raises(self):
        with self.assertRaises(ValueRangeError):
            Seq([1, 2.5])

    def test_bool_is_not_integer(self):
        with self.assertRaises(ValueRangeError):
            Seq([1, True])

    def test_non_iterable_raises(self):
        with self.assertRaises(ValueRangeError):
            Seq(3)


class TestAccess(unittest.TestCase):
    def test_get(self):
        seq = Seq([10, 20, 30])
        self.assertEqual(seq.get(0), 10)
        self.assertEqual(seq.get(2), 30)

    def test_set(self):
        seq = Seq([10, 20, 30])
        seq.set(1, 99)
        self.assertEqual(seq.to_list(), [10, 99, 30])

    def test_get_out_of_range(self):
        seq = Seq([1, 2])
        with self.assertRaises(IndexOutOfRangeError):
            seq.get(2)

    def test_set_out_of_range(self):
        seq = Seq([1, 2])
        with self.assertRaises(IndexOutOfRangeError):
            seq.set(2, 5)

    def test_negative_index_rejected(self):
        seq = Seq([1, 2])
        with self.assertRaises(IndexOutOfRangeError):
            seq.get(-1)

    def test_get_on_empty(self):
        with self.assertRaises(IndexOutOfRangeError):
            Seq().get(0)

    def test_set_non_integer(self):
        seq = Seq([1, 2])
        with self.assertRaises(ValueRangeError):
            seq.set(0, "x")


class TestInsertDelete(unittest.TestCase):
    def test_insert_at_front(self):
        seq = Seq([1, 2, 3])
        seq.insert(0, 9)
        self.assertEqual(seq.to_list(), [9, 1, 2, 3])

    def test_insert_in_middle(self):
        seq = Seq([1, 2, 3])
        seq.insert(2, 9)
        self.assertEqual(seq.to_list(), [1, 2, 9, 3])

    def test_insert_at_end(self):
        seq = Seq([1, 2, 3])
        seq.insert(3, 9)
        self.assertEqual(seq.to_list(), [1, 2, 3, 9])

    def test_insert_into_empty(self):
        seq = Seq()
        seq.insert(0, 7)
        self.assertEqual(seq.to_list(), [7])

    def test_insert_position_past_end(self):
        seq = Seq([1, 2])
        with self.assertRaises(IndexOutOfRangeError):
            seq.insert(3, 9)

    def test_insert_negative_position(self):
        seq = Seq([1, 2])
        with self.assertRaises(IndexOutOfRangeError):
            seq.insert(-1, 9)

    def test_insert_non_integer(self):
        seq = Seq([1, 2])
        with self.assertRaises(ValueRangeError):
            seq.insert(0, 1.5)

    def test_delete_returns_value(self):
        seq = Seq([1, 2, 3])
        self.assertEqual(seq.delete(1), 2)
        self.assertEqual(seq.to_list(), [1, 3])

    def test_delete_front(self):
        seq = Seq([1, 2, 3])
        seq.delete(0)
        self.assertEqual(seq.to_list(), [2, 3])

    def test_delete_to_empty(self):
        seq = Seq([5])
        self.assertEqual(seq.delete(0), 5)
        self.assertTrue(seq.is_empty())

    def test_delete_out_of_range(self):
        seq = Seq([1, 2])
        with self.assertRaises(IndexOutOfRangeError):
            seq.delete(2)

    def test_delete_on_empty(self):
        with self.assertRaises(IndexOutOfRangeError):
            Seq().delete(0)


class TestReverse(unittest.TestCase):
    def test_reverse_middle(self):
        seq = Seq([1, 2, 3, 4, 5])
        seq.reverse(1, 4)
        self.assertEqual(seq.to_list(), [1, 4, 3, 2, 5])

    def test_reverse_whole(self):
        seq = Seq([1, 2, 3])
        seq.reverse(0, 3)
        self.assertEqual(seq.to_list(), [3, 2, 1])

    def test_reverse_empty_range(self):
        seq = Seq([1, 2, 3])
        seq.reverse(1, 1)
        self.assertEqual(seq.to_list(), [1, 2, 3])

    def test_reverse_single(self):
        seq = Seq([1, 2, 3])
        seq.reverse(1, 2)
        self.assertEqual(seq.to_list(), [1, 2, 3])

    def test_reverse_twice_restores(self):
        seq = Seq([1, 2, 3, 4])
        seq.reverse(0, 4)
        seq.reverse(0, 4)
        self.assertEqual(seq.to_list(), [1, 2, 3, 4])

    def test_reverse_bad_range(self):
        seq = Seq([1, 2, 3])
        with self.assertRaises(InvalidRangeError):
            seq.reverse(2, 1)


class TestRangeAdd(unittest.TestCase):
    def test_add_middle(self):
        seq = Seq([1, 2, 3, 4])
        seq.add(1, 3, 10)
        self.assertEqual(seq.to_list(), [1, 12, 13, 4])

    def test_add_negative_delta(self):
        seq = Seq([1, 2, 3])
        seq.add(0, 3, -1)
        self.assertEqual(seq.to_list(), [0, 1, 2])

    def test_add_whole(self):
        seq = Seq([1, 2, 3])
        seq.add(0, 3, 5)
        self.assertEqual(seq.to_list(), [6, 7, 8])

    def test_add_empty_range_is_noop(self):
        seq = Seq([1, 2, 3])
        seq.add(1, 1, 100)
        self.assertEqual(seq.to_list(), [1, 2, 3])

    def test_add_non_integer_delta(self):
        seq = Seq([1, 2, 3])
        with self.assertRaises(ValueRangeError):
            seq.add(0, 2, 1.5)

    def test_add_bad_range(self):
        seq = Seq([1, 2, 3])
        with self.assertRaises(InvalidRangeError):
            seq.add(0, 5, 1)


class TestRangeStats(unittest.TestCase):
    def test_sum_middle(self):
        self.assertEqual(Seq([1, 2, 3, 4]).sum(1, 3), 5)

    def test_sum_empty_range(self):
        self.assertEqual(Seq([1, 2, 3]).sum(1, 1), 0)

    def test_sum_whole(self):
        self.assertEqual(Seq([1, 2, 3]).sum(0, 3), 6)

    def test_min_middle(self):
        self.assertEqual(Seq([4, 2, 7, 1]).min(1, 3), 2)

    def test_max_middle(self):
        self.assertEqual(Seq([4, 2, 7, 1]).max(1, 3), 7)

    def test_min_empty_range_raises(self):
        with self.assertRaises(EmptySequenceError):
            Seq([1, 2, 3]).min(1, 1)

    def test_max_empty_range_raises(self):
        with self.assertRaises(EmptySequenceError):
            Seq([1, 2, 3]).max(2, 2)

    def test_stats_bad_range(self):
        seq = Seq([1, 2, 3])
        with self.assertRaises(InvalidRangeError):
            seq.sum(0, 4)


class TestReplay(unittest.TestCase):
    def test_replay_mixed(self):
        final, results = replay(
            [1, 2, 3],
            [
                ("insert", 1, 9),
                ("reverse", 0, 2),
                ("add", 0, 3, 1),
                ("sum", 0, 3),
                ("min", 0, 3),
            ],
        )
        self.assertEqual(final, [10, 2, 3, 3])
        self.assertEqual(results[-2], 15)
        self.assertEqual(results[-1], 2)

    def test_replay_delete_returns(self):
        final, results = replay([1, 2, 3], [("delete", 0), ("get", 0)])
        self.assertEqual(results, [1, 2])
        self.assertEqual(final, [2, 3])


class TestExceptionHierarchy(unittest.TestCase):
    def test_all_inherit_base(self):
        for exc in (IndexOutOfRangeError, EmptySequenceError,
                    InvalidRangeError, ValueRangeError):
            self.assertTrue(issubclass(exc, SeqError))

    def test_catchable_via_base(self):
        with self.assertRaises(SeqError):
            Seq([1, 2]).get(5)


class TestDeterminism(unittest.TestCase):
    def test_same_operations_repeatable(self):
        operations = [
            ("insert", 0, 5),
            ("reverse", 0, 2),
            ("add", 0, 2, 3),
            ("delete", 1),
        ]
        first = replay([1, 2, 3], operations)
        second = replay([1, 2, 3], operations)
        self.assertEqual(first, second)

    def test_independent_instances(self):
        a = Seq([1, 2, 3])
        b = Seq([1, 2, 3])
        a.add(0, 3, 10)
        self.assertEqual(b.to_list(), [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
