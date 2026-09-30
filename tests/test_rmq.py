"""NaiveRMQ 现状行为的锁定测试（改造前基线，不许改）。

这些用例锁住朴素实现的现状行为：构造校验、按次逐项扫描得到的
最小值、最大值、最小值首次出现的下标、批量结果，以及全部边界口径。
测试一个字不改，改造后必须仍然全绿。
"""

import unittest

from sparsetable.rmq import Erro, IllegalArgument, NaiveRMQ


class TestBasics(unittest.TestCase):
    def test_length(self):
        q = NaiveRMQ([3, 1, 4, 1, 5])
        self.assertEqual(len(q), 5)

    def test_value_at(self):
        q = NaiveRMQ([3, 1, 4])
        self.assertEqual(q.value_at(0), 3)
        self.assertEqual(q.value_at(2), 4)

    def test_value_at_out_of_range_raises(self):
        q = NaiveRMQ([3, 1, 4])
        with self.assertRaises(IllegalArgument):
            q.value_at(3)
        with self.assertRaises(IllegalArgument):
            q.value_at(-1)

    def test_value_at_non_int_raises(self):
        q = NaiveRMQ([3, 1, 4])
        with self.assertRaises(IllegalArgument):
            q.value_at(True)
        with self.assertRaises(IllegalArgument):
            q.value_at(None)

    def test_as_list_is_a_copy(self):
        q = NaiveRMQ([3, 1, 4])
        snapshot = q.as_list()
        snapshot.append(99)
        self.assertEqual(q.as_list(), [3, 1, 4])

    def test_constructor_rejects_bad_input(self):
        with self.assertRaises(IllegalArgument):
            NaiveRMQ("abc")
        with self.assertRaises(IllegalArgument):
            NaiveRMQ([1, True, 2])
        with self.assertRaises(IllegalArgument):
            NaiveRMQ([1, 2.5, 3])


class TestQueryMin(unittest.TestCase):
    def test_single_element(self):
        q = NaiveRMQ([7])
        self.assertEqual(q.query_min(0, 1), 7)

    def test_full_range(self):
        q = NaiveRMQ([3, 1, 4, 1, 5])
        self.assertEqual(q.query_min(0, 5), 1)

    def test_general_range(self):
        q = NaiveRMQ([3, 1, 4, 1, 5])
        self.assertEqual(q.query_min(1, 3), 1)
        self.assertEqual(q.query_min(2, 5), 1)

    def test_all_equal(self):
        q = NaiveRMQ([4, 4, 4, 4])
        self.assertEqual(q.query_min(0, 4), 4)

    def test_negative_values(self):
        q = NaiveRMQ([-3, -7, -1])
        self.assertEqual(q.query_min(0, 3), -7)
        self.assertEqual(q.query_min(1, 3), -7)

    def test_empty_range_returns_none(self):
        q = NaiveRMQ([3, 1, 4])
        self.assertIsNone(q.query_min(2, 2))

    def test_empty_sequence(self):
        q = NaiveRMQ([])
        self.assertIsNone(q.query_min(0, 0))

    def test_left_greater_right_raises(self):
        q = NaiveRMQ([3, 1, 4])
        with self.assertRaises(IllegalArgument):
            q.query_min(2, 1)

    def test_out_of_range_raises(self):
        q = NaiveRMQ([3, 1, 4])
        with self.assertRaises(IllegalArgument):
            q.query_min(0, 4)
        with self.assertRaises(IllegalArgument):
            q.query_min(-1, 2)

    def test_none_endpoint_raises(self):
        q = NaiveRMQ([3, 1, 4])
        with self.assertRaises(IllegalArgument):
            q.query_min(None, 2)


class TestQueryMax(unittest.TestCase):
    def test_full_range(self):
        q = NaiveRMQ([3, 1, 4, 1, 5])
        self.assertEqual(q.query_max(0, 5), 5)

    def test_general_range(self):
        q = NaiveRMQ([3, 1, 4, 1, 5])
        self.assertEqual(q.query_max(0, 3), 4)
        self.assertEqual(q.query_max(3, 5), 5)

    def test_negative_values(self):
        q = NaiveRMQ([-3, -7, -1])
        self.assertEqual(q.query_max(0, 3), -1)

    def test_empty_range_returns_none(self):
        q = NaiveRMQ([3, 1, 4])
        self.assertIsNone(q.query_max(1, 1))

    def test_out_of_range_raises(self):
        q = NaiveRMQ([3, 1, 4])
        with self.assertRaises(IllegalArgument):
            q.query_max(0, 5)


class TestQueryArgmin(unittest.TestCase):
    def test_returns_first_occurrence_index(self):
        q = NaiveRMQ([3, 1, 4, 1, 5])
        self.assertEqual(q.query_argmin(0, 5), 1)
        self.assertEqual(q.query_argmin(1, 4), 1)

    def test_single_element(self):
        q = NaiveRMQ([9, 2, 7])
        self.assertEqual(q.query_argmin(1, 2), 1)

    def test_returns_absolute_index(self):
        q = NaiveRMQ([9, 2, 7, 2])
        self.assertEqual(q.query_argmin(1, 4), 1)
        self.assertEqual(q.query_argmin(2, 4), 3)

    def test_empty_range_returns_none(self):
        q = NaiveRMQ([3, 1, 4])
        self.assertIsNone(q.query_argmin(0, 0))

    def test_out_of_range_raises(self):
        q = NaiveRMQ([3, 1, 4])
        with self.assertRaises(IllegalArgument):
            q.query_argmin(0, 4)


class TestQueryMany(unittest.TestCase):
    def test_batch_matches_single(self):
        q = NaiveRMQ([5, 2, 8, 1, 9, 3])
        ranges = [(0, 6), (0, 1), (1, 3), (2, 2), (4, 6)]
        self.assertEqual(q.query_many(ranges), [1, 5, 2, None, 3])

    def test_batch_empty(self):
        q = NaiveRMQ([1, 2, 3])
        self.assertEqual(q.query_many([]), [])


class TestErrorBase(unittest.TestCase):
    def test_all_errors_share_base(self):
        self.assertTrue(issubclass(IllegalArgument, Erro))

    def test_catch_by_base(self):
        with self.assertRaises(Erro):
            NaiveRMQ([1, 2, 3]).query_min(0, 9)


if __name__ == "__main__":
    unittest.main()
