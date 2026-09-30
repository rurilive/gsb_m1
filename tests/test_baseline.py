"""基线测试：锁住朴素逐询问重扫实现的现状行为，升级后一字不许改且必须全绿。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from morollback import (  # noqa: E402
    Erro,
    IntervalStats,
    InvalidArgumentError,
    InvalidQueryError,
    collapsed_intervals,
    normalize_queries,
    prepare,
    scan_steps,
)

VALUES = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5, 8]


class NormalizeTest(unittest.TestCase):
    def test_keeps_order_and_pairs(self):
        self.assertEqual(normalize_queries([(3, 7), (0, 2)]), [(3, 7), (0, 2)])

    def test_accepts_lists(self):
        self.assertEqual(normalize_queries([[3, 7]]), [(3, 7)])

    def test_empty_interval_becomes_zero_negative_one(self):
        self.assertEqual(normalize_queries([(4, 1)]), [(0, -1)])

    def test_rejects_bad_shape(self):
        with self.assertRaises(InvalidQueryError):
            normalize_queries("5")
        with self.assertRaises(InvalidQueryError):
            normalize_queries([(1, 2, 3)])
        with self.assertRaises(InvalidQueryError):
            normalize_queries([(-1, 3)])
        with self.assertRaises(InvalidQueryError):
            normalize_queries([(1, -3)])

    def test_rejects_bad_argument(self):
        with self.assertRaises(InvalidArgumentError):
            normalize_queries(None)
        with self.assertRaises(InvalidArgumentError):
            normalize_queries([(True, 5)])


class CollapseAndStepsTest(unittest.TestCase):
    def test_collapse_sorts_by_left_then_right(self):
        got = collapsed_intervals([(5, 5), (1, 3), (1, 1), (3, 7), (4, 1)])
        self.assertEqual(got, [(0, -1), (1, 1), (1, 3), (3, 7), (5, 5)])

    def test_scan_steps_counts_positions(self):
        self.assertEqual(scan_steps(VALUES, [(3, 7), (0, 11), (4, 1), (2, 2)]), 18)

    def test_scan_steps_empty_query_set(self):
        self.assertEqual(scan_steps(VALUES, []), 0)

    def test_prepare_length(self):
        self.assertEqual(prepare(VALUES).length(), 12)
        self.assertEqual(prepare([]).length(), 0)


class IntervalStatsTest(unittest.TestCase):
    def setUp(self):
        self.stats = IntervalStats(VALUES)

    def test_query_distinct(self):
        self.assertEqual(self.stats.query_distinct(3, 7), 5)
        self.assertEqual(self.stats.query_distinct(0, 11), 8)
        self.assertEqual(self.stats.query_distinct(0, 0), 1)
        self.assertEqual(self.stats.query_distinct(7, 3), 0)

    def test_query_mode_tie_breaks_smallest(self):
        self.assertEqual(self.stats.query_mode(3, 7), 1)
        self.assertEqual(self.stats.query_mode(0, 11), 5)
        self.assertEqual(self.stats.query_mode(0, 4), 1)
        self.assertEqual(self.stats.query_mode(3, 3), 1)
        self.assertIsNone(self.stats.query_mode(4, 1))

    def test_query_maxfreq(self):
        self.assertEqual(self.stats.query_maxfreq(0, 11), 3)
        self.assertEqual(self.stats.query_maxfreq(0, 4), 2)
        self.assertEqual(self.stats.query_maxfreq(3, 7), 1)
        self.assertEqual(self.stats.query_maxfreq(4, 1), 0)

    def test_query_count(self):
        self.assertEqual(self.stats.query_count(0, 11, 5), 3)
        self.assertEqual(self.stats.query_count(5, 11, 5), 2)
        self.assertEqual(self.stats.query_count(3, 7, 9), 1)
        self.assertEqual(self.stats.query_count(0, 11, 99), 0)

    def test_query_range(self):
        self.assertEqual(self.stats.query_range(3, 7), 8)
        self.assertEqual(self.stats.query_range(0, 2), 3)
        self.assertEqual(self.stats.query_range(0, 11), 8)
        self.assertIsNone(self.stats.query_range(4, 1))

    def test_answer_fields(self):
        rec = self.stats.answer(3, 7)
        self.assertEqual(rec["length"], 5)
        self.assertEqual(rec["distinct"], 5)
        self.assertEqual(rec["mode"], 1)
        self.assertEqual(rec["maxfreq"], 1)
        self.assertEqual(rec["range"], 8)

    def test_answer_on_empty_interval(self):
        rec = self.stats.answer(4, 1)
        self.assertEqual(rec["left"], 4)
        self.assertEqual(rec["right"], 1)
        self.assertEqual(rec["length"], 0)
        self.assertEqual(rec["distinct"], 0)
        self.assertIsNone(rec["mode"])
        self.assertEqual(rec["maxfreq"], 0)
        self.assertIsNone(rec["range"])

    def test_run_checksum_and_length(self):
        answers, checksum = self.stats.run([(3, 7), (4, 1), (7, 3)])
        self.assertEqual(len(answers), 3)
        self.assertEqual(answers[0]["distinct"], 5)
        self.assertEqual(checksum, 25)

    def test_run_on_empty_query_set(self):
        answers, checksum = self.stats.run([])
        self.assertEqual(answers, [])
        self.assertEqual(checksum, 0)

    def test_out_of_range_endpoint(self):
        with self.assertRaises(InvalidQueryError):
            self.stats.query_distinct(0, 12)
        with self.assertRaises(Erro):
            self.stats.query_range(-1, 3)


class ScaleAndDeterminismTest(unittest.TestCase):
    def test_scan_steps_grow_with_more_queries(self):
        one = scan_steps(VALUES, [(0, 11)])
        many = scan_steps(VALUES, [(0, 11), (0, 11), (0, 11)])
        self.assertLess(one, many)
        self.assertEqual(one, 12)
        self.assertEqual(many, 36)

    def test_repeatable(self):
        first = IntervalStats(VALUES).run([(3, 7), (0, 11)])
        second = IntervalStats(VALUES).run([(3, 7), (0, 11)])
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
