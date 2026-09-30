"""RangeSeq 现状行为的锁定测试（基线，一字不改且必须全绿）。

锁的是一个固定序列上朴素重扫的区间求和、区间加、区间赋值、区间最值、
单点读改、操作回放与访问计数的结果，以及非法下标必须 fail fast。
"""

import unittest

from rangeseg.seq import (
    EmptySequenceError,
    IndexOutOfRangeError,
    RangeSegError,
    RangeSeq,
)

# 固定序列：
#   下标  0   1   2   3   4   5   6   7
#   值    3  -1   4   1   5  -9   2   6
FIXED_DATA = [3, -1, 4, 1, 5, -9, 2, 6]


def build():
    return RangeSeq(FIXED_DATA)


class TestStructure(unittest.TestCase):
    def test_size(self):
        self.assertEqual(build().size(), 8)

    def test_data_returns_copy(self):
        s = build()
        got = s.data
        got.append(999)
        self.assertEqual(s.data, FIXED_DATA)

    def test_empty_sequence(self):
        s = RangeSeq()
        self.assertEqual(s.size(), 0)
        self.assertEqual(s.sum(0, 0), 0)


class TestSum(unittest.TestCase):
    def test_full_range(self):
        self.assertEqual(build().sum(0, 8), 11)

    def test_small_ranges(self):
        s = build()
        self.assertEqual(s.sum(0, 3), 6)
        self.assertEqual(s.sum(2, 5), 10)
        self.assertEqual(s.sum(5, 6), -9)
        self.assertEqual(s.sum(3, 7), -1)

    def test_empty_range(self):
        self.assertEqual(build().sum(4, 4), 0)


class TestAdd(unittest.TestCase):
    def test_add_then_sum(self):
        s = build()
        s.add(1, 4, 10)
        self.assertEqual(s.data, [3, 9, 14, 11, 5, -9, 2, 6])
        self.assertEqual(s.sum(1, 4), 34)

    def test_add_returns_self(self):
        s = build()
        self.assertIs(s.add(0, 1, 1), s)

    def test_add_empty_is_noop(self):
        s = build()
        s.add(3, 3, 100)
        self.assertEqual(s.data, FIXED_DATA)

    def test_add_negative_delta(self):
        s = build()
        s.add(4, 6, -5)
        self.assertEqual(s.data, [3, -1, 4, 1, 0, -14, 2, 6])


class TestAssign(unittest.TestCase):
    def test_assign_then_sum(self):
        s = build()
        s.assign(1, 4, 7)
        self.assertEqual(s.data, [3, 7, 7, 7, 5, -9, 2, 6])
        self.assertEqual(s.sum(0, 8), 28)

    def test_assign_overwrites_adds(self):
        s = build()
        s.add(2, 6, 10)
        s.assign(3, 5, 0)
        self.assertEqual(s.data, [3, -1, 14, 0, 0, 1, 2, 6])

    def test_assign_returns_self(self):
        s = build()
        self.assertIs(s.assign(0, 1, 5), s)


class TestMinMax(unittest.TestCase):
    def test_min_full(self):
        self.assertEqual(build().min_val(0, 8), -9)

    def test_max_full(self):
        self.assertEqual(build().max_val(0, 8), 6)

    def test_min_max_small(self):
        s = build()
        self.assertEqual(s.min_val(0, 3), -1)
        self.assertEqual(s.max_val(0, 3), 4)
        self.assertEqual(s.min_val(6, 8), 2)
        self.assertEqual(s.max_val(2, 4), 4)

    def test_min_single(self):
        self.assertEqual(build().min_val(4, 5), 5)

    def test_empty_min_raises(self):
        with self.assertRaises(EmptySequenceError):
            build().min_val(3, 3)

    def test_empty_max_raises(self):
        with self.assertRaises(EmptySequenceError):
            build().max_val(7, 7)


class TestPointOps(unittest.TestCase):
    def test_get(self):
        s = build()
        self.assertEqual(s.get(0), 3)
        self.assertEqual(s.get(5), -9)
        self.assertEqual(s.get(7), 6)

    def test_set(self):
        s = build()
        s.set(2, 40)
        self.assertEqual(s.get(2), 40)
        self.assertEqual(s.sum(0, 8), 47)

    def test_set_returns_self(self):
        s = build()
        self.assertIs(s.set(0, 0), s)


class TestTakenCounter(unittest.TestCase):
    def test_fresh_counter_is_zero(self):
        self.assertEqual(build().taken(), 0)

    def test_sum_counts_scan_length(self):
        s = build()
        s.sum(2, 5)
        self.assertEqual(s.taken(), 3)

    def test_counters_accumulate(self):
        s = build()
        s.sum(0, 8)
        s.min_val(0, 8)
        self.assertEqual(s.taken(), 16)


class TestReplay(unittest.TestCase):
    def test_replay_matches_step_by_step(self):
        ops = [
            ("sum", 0, 8),
            ("add", 0, 2, 1),
            ("min", 0, 4),
            ("max", 0, 4),
            ("set", 3, 100),
            ("get", 3),
            ("sum", 3, 5),
        ]
        final, results = RangeSeq.replay(FIXED_DATA, ops)
        self.assertEqual(results, [11, None, 0, 4, None, 100, 105])
        self.assertEqual(final, [4, 0, 4, 100, 5, -9, 2, 6])

    def test_replay_with_assign(self):
        ops = [
            ("assign", 0, 3, 2),
            ("sum", 0, 8),
            ("add", 0, 8, 1),
            ("max", 0, 8),
        ]
        final, results = RangeSeq.replay(FIXED_DATA, ops)
        self.assertEqual(results, [None, 11, None, 7])
        self.assertEqual(final, [3, 3, 3, 2, 6, -8, 3, 7])

    def test_replay_does_not_touch_source(self):
        source = list(FIXED_DATA)
        RangeSeq.replay(source, [("add", 0, 8, 5)])
        self.assertEqual(source, FIXED_DATA)

    def test_replay_unknown_op_raises(self):
        with self.assertRaises(RangeSegError):
            RangeSeq.replay(FIXED_DATA, [("nope",)])


class TestBadIndices(unittest.TestCase):
    def test_negative_left(self):
        with self.assertRaises(IndexOutOfRangeError):
            build().sum(-1, 3)

    def test_right_beyond_size(self):
        with self.assertRaises(IndexOutOfRangeError):
            build().add(0, 9, 1)

    def test_reversed_range(self):
        with self.assertRaises(IndexOutOfRangeError):
            build().min_val(5, 2)

    def test_assign_reversed_range(self):
        with self.assertRaises(IndexOutOfRangeError):
            build().assign(6, 2, 0)

    def test_get_out_of_range(self):
        with self.assertRaises(IndexOutOfRangeError):
            build().get(8)

    def test_set_out_of_range(self):
        with self.assertRaises(IndexOutOfRangeError):
            build().set(-1, 0)

    def test_bad_index_is_rangeseg_error(self):
        self.assertTrue(issubclass(IndexOutOfRangeError, RangeSegError))

    def test_empty_min_is_rangeseg_error(self):
        self.assertTrue(issubclass(EmptySequenceError, RangeSegError))

    def test_reversed_range_is_rangeseg_error(self):
        with self.assertRaises(RangeSegError):
            build().sum(7, 3)


if __name__ == "__main__":
    unittest.main()
