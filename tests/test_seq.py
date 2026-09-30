"""Sequence 现状行为的锁定测试（基线，一字不改且必须全绿）。

锁的是一个固定序列上朴素逐元素处理的区间求和、区间加、区间最大值、
区间计数、单点读改与操作回放的结果，元素访问计数的口径，以及非法区间
与非法下标必须 fail fast。
"""

import unittest

from sqrtds.seq import (
    EmptyRangeError,
    IndexOutOfRangeError,
    Sequence,
    SqrtdsError,
)

# 固定序列：
#   下标  0   1   2   3   4   5   6   7
#   值    3  -1   4   1   5  -9   2   6
FIXED_DATA = [3, -1, 4, 1, 5, -9, 2, 6]


def build():
    return Sequence(FIXED_DATA)


class TestStructure(unittest.TestCase):
    def test_size(self):
        self.assertEqual(build().size(), 8)

    def test_data_returns_copy(self):
        s = build()
        got = s.data
        got.append(999)
        self.assertEqual(s.data, FIXED_DATA)

    def test_empty_sequence(self):
        s = Sequence()
        self.assertEqual(s.size(), 0)
        self.assertEqual(s.sum_range(0, 0), 0)

    def test_fresh_touches_zero(self):
        self.assertEqual(build().element_touches, 0)


class TestSum(unittest.TestCase):
    def test_full_range(self):
        self.assertEqual(build().sum_range(0, 8), 11)

    def test_small_ranges(self):
        s = build()
        self.assertEqual(s.sum_range(0, 3), 6)
        self.assertEqual(s.sum_range(2, 5), 10)
        self.assertEqual(s.sum_range(5, 6), -9)
        self.assertEqual(s.sum_range(3, 7), -1)

    def test_empty_range(self):
        self.assertEqual(build().sum_range(4, 4), 0)

    def test_single_element_range(self):
        self.assertEqual(build().sum_range(5, 6), -9)


class TestAdd(unittest.TestCase):
    def test_add_then_sum(self):
        s = build()
        s.add_range(1, 4, 10)
        self.assertEqual(s.data, [3, 9, 14, 11, 5, -9, 2, 6])
        self.assertEqual(s.sum_range(1, 4), 34)

    def test_add_returns_self(self):
        s = build()
        self.assertIs(s.add_range(0, 1, 1), s)

    def test_add_empty_is_noop(self):
        s = build()
        s.add_range(3, 3, 100)
        self.assertEqual(s.data, FIXED_DATA)

    def test_add_negative_delta(self):
        s = build()
        s.add_range(4, 6, -5)
        self.assertEqual(s.data, [3, -1, 4, 1, 0, -14, 2, 6])

    def test_add_zero(self):
        s = build()
        s.add_range(0, 8, 0)
        self.assertEqual(s.data, FIXED_DATA)

    def test_add_accumulates(self):
        s = build()
        s.add_range(0, 8, 1)
        s.add_range(0, 8, 2)
        self.assertEqual(s.data, [6, 2, 7, 4, 8, -6, 5, 9])


class TestMax(unittest.TestCase):
    def test_max_full(self):
        self.assertEqual(build().max_range(0, 8), 6)

    def test_max_small(self):
        s = build()
        self.assertEqual(s.max_range(0, 3), 4)
        self.assertEqual(s.max_range(2, 4), 4)
        self.assertEqual(s.max_range(6, 8), 6)

    def test_max_negative_values(self):
        s = Sequence([-5, -3, -9, -1])
        self.assertEqual(s.max_range(0, 4), -1)

    def test_max_single(self):
        self.assertEqual(build().max_range(4, 5), 5)

    def test_empty_max_raises(self):
        with self.assertRaises(EmptyRangeError):
            build().max_range(3, 3)


class TestCount(unittest.TestCase):
    def test_count_present(self):
        s = build()
        self.assertEqual(s.count_range(0, 8, 1), 1)
        self.assertEqual(s.count_range(0, 8, 5), 1)

    def test_count_absent(self):
        self.assertEqual(build().count_range(0, 8, 100), 0)

    def test_count_partial(self):
        s = Sequence([1, 2, 1, 1, 3])
        self.assertEqual(s.count_range(0, 5, 1), 3)
        self.assertEqual(s.count_range(1, 4, 1), 2)

    def test_count_empty(self):
        self.assertEqual(build().count_range(2, 2, 1), 0)

    def test_count_after_add(self):
        s = build()
        s.add_range(0, 8, 1)
        self.assertEqual(s.count_range(0, 8, 2), 1)


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
        self.assertEqual(s.sum_range(0, 8), 47)

    def test_set_returns_self(self):
        s = build()
        self.assertIs(s.set(0, 0), s)


class TestTouches(unittest.TestCase):
    def test_touches_count_elements(self):
        s = build()
        s.sum_range(2, 5)
        self.assertEqual(s.element_touches, 3)
        s.add_range(0, 4, 1)
        self.assertEqual(s.element_touches, 7)

    def test_touches_include_max_and_get(self):
        s = build()
        s.max_range(0, 4)
        self.assertEqual(s.element_touches, 4)
        s.get(7)
        self.assertEqual(s.element_touches, 5)

    def test_reset_touches(self):
        s = build()
        s.sum_range(0, 8)
        self.assertIs(s.reset_touches(), s)
        self.assertEqual(s.element_touches, 0)


class TestReplay(unittest.TestCase):
    def test_replay_matches_step_by_step(self):
        ops = [
            ("sum", 0, 8),
            ("add", 0, 2, 1),
            ("max", 0, 4),
            ("count", 0, 8, 1),
            ("set", 3, 100),
            ("get", 3),
            ("sum", 3, 5),
        ]
        final, results = Sequence.replay(FIXED_DATA, ops)
        self.assertEqual(results, [11, None, 4, 1, None, 100, 105])
        self.assertEqual(final, [4, 0, 4, 100, 5, -9, 2, 6])

    def test_replay_does_not_touch_source(self):
        source = list(FIXED_DATA)
        Sequence.replay(source, [("add", 0, 8, 5)])
        self.assertEqual(source, FIXED_DATA)

    def test_replay_unknown_op_raises(self):
        with self.assertRaises(SqrtdsError):
            Sequence.replay(FIXED_DATA, [("nope",)])


class TestBadIndices(unittest.TestCase):
    def test_negative_left(self):
        with self.assertRaises(IndexOutOfRangeError):
            build().sum_range(-1, 3)

    def test_right_beyond_size(self):
        with self.assertRaises(IndexOutOfRangeError):
            build().add_range(0, 9, 1)

    def test_reversed_range(self):
        with self.assertRaises(IndexOutOfRangeError):
            build().max_range(5, 2)

    def test_count_reversed_range(self):
        with self.assertRaises(IndexOutOfRangeError):
            build().count_range(6, 2, 1)

    def test_get_out_of_range(self):
        with self.assertRaises(IndexOutOfRangeError):
            build().get(8)

    def test_set_out_of_range(self):
        with self.assertRaises(IndexOutOfRangeError):
            build().set(-1, 0)

    def test_bad_index_is_sqrtds_error(self):
        self.assertTrue(issubclass(IndexOutOfRangeError, SqrtdsError))

    def test_empty_max_is_sqrtds_error(self):
        self.assertTrue(issubclass(EmptyRangeError, SqrtdsError))

    def test_reversed_range_is_sqrtds_error(self):
        with self.assertRaises(SqrtdsError):
            build().sum_range(7, 3)


if __name__ == "__main__":
    unittest.main()
