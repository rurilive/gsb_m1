"""NaiveIntervalScheduler 现有行为的锁定测试（穷举全部子集口径）。"""

import unittest

from ivsched.core import (
    BadInterval,
    BadWeight,
    Erro,
    NaiveIntervalScheduler,
    UnknownInterval,
)


def demo_input():
    """三个区间：0 与 1 重叠，2 与两者都不重叠。"""
    s = NaiveIntervalScheduler()
    s.add(0, 5, 1)
    s.add(3, 8, 1)
    s.add(10, 12, 1)
    return s


class TestAdd(unittest.TestCase):
    def test_add_returns_index(self):
        s = NaiveIntervalScheduler()
        self.assertEqual(s.add(0, 5), 0)
        self.assertEqual(s.add(6, 9), 1)

    def test_size_and_intervals(self):
        s = demo_input()
        self.assertEqual(s.size(), 3)
        self.assertEqual(s.intervals(), [(0, 0, 5, 1), (1, 3, 8, 1), (2, 10, 12, 1)])

    def test_interval_getter(self):
        s = demo_input()
        self.assertEqual(s.interval(1), (3, 8, 1))

    def test_unknown_interval_rejected(self):
        s = demo_input()
        with self.assertRaises(UnknownInterval):
            s.interval(9)

    def test_negative_index_rejected(self):
        s = demo_input()
        with self.assertRaises(UnknownInterval):
            s.interval(-1)

    def test_non_int_endpoint_rejected(self):
        s = NaiveIntervalScheduler()
        with self.assertRaises(BadInterval):
            s.add(0.5, 3)

    def test_start_after_end_rejected(self):
        s = NaiveIntervalScheduler()
        with self.assertRaises(BadInterval):
            s.add(9, 4)

    def test_bad_interval_is_base_error(self):
        s = NaiveIntervalScheduler()
        with self.assertRaises(Erro):
            s.add("a", 4)

    def test_non_int_weight_rejected(self):
        s = NaiveIntervalScheduler()
        with self.assertRaises(BadWeight):
            s.add(0, 4, 1.5)

    def test_negative_weight_rejected(self):
        s = NaiveIntervalScheduler()
        with self.assertRaises(BadWeight):
            s.add(0, 4, -1)

    def test_bad_weight_is_base_error(self):
        s = NaiveIntervalScheduler()
        with self.assertRaises(Erro):
            s.add(0, 4, True)

    def test_singleton_interval_ok(self):
        s = NaiveIntervalScheduler()
        self.assertEqual(s.add(7, 7), 0)
        self.assertEqual(s.interval(0), (7, 7, 1))


class TestOverlap(unittest.TestCase):
    def test_touching_endpoints_overlap(self):
        s = demo_input()
        self.assertTrue(s.overlaps(0, 0))

    def test_equal_endpoints_overlap(self):
        s = NaiveIntervalScheduler()
        s.add(0, 5)
        s.add(5, 9)
        self.assertTrue(s.overlaps(0, 1))

    def test_disjoint_when_gap(self):
        s = demo_input()
        self.assertFalse(s.overlaps(0, 2))


class TestSelections(unittest.TestCase):
    def test_all_selections_include_empty(self):
        s = demo_input()
        self.assertIn((), s.all_disjoint_selections())

    def test_all_selections_count(self):
        s = demo_input()
        # 空集、三个单点、以及 0 与 2、1 与 2、再算上三者不可共存
        self.assertEqual(
            sorted(s.all_disjoint_selections()),
            [(), (0,), (0, 2), (1,), (1, 2), (2,)],
        )

    def test_max_disjoint_count(self):
        s = demo_input()
        self.assertEqual(s.max_disjoint_count(), 2)

    def test_max_disjoint_count_empty(self):
        s = NaiveIntervalScheduler()
        self.assertEqual(s.max_disjoint_count(), 0)

    def test_best_disjoint_selection_len(self):
        s = demo_input()
        self.assertEqual(len(s.best_disjoint_selection()), 2)

    def test_best_disjoint_selection_lexicographic(self):
        s = demo_input()
        # (0, 2) 与 (1, 2) 都是两个，取字典序最小者
        self.assertEqual(s.best_disjoint_selection(), (0, 2))

    def test_max_weighted_value(self):
        s = NaiveIntervalScheduler()
        s.add(0, 5, 2)
        s.add(3, 8, 3)
        s.add(10, 12, 4)
        # 取 1 与 2 得 7，胜过 0 与 2 的 6
        self.assertEqual(s.max_weighted_value(), 7)

    def test_best_weighted_selection(self):
        s = NaiveIntervalScheduler()
        s.add(0, 5, 2)
        s.add(3, 8, 3)
        s.add(10, 12, 4)
        self.assertEqual(s.best_weighted_selection(), (1, 2))

    def test_weighted_ties_pick_lexicographic_smallest(self):
        s = NaiveIntervalScheduler()
        s.add(0, 5, 5)
        s.add(0, 5, 5)
        # 两个同寸同重的单点，取下标更小者
        self.assertEqual(s.best_weighted_selection(), (0,))

    def test_identical_intervals_conflict(self):
        s = NaiveIntervalScheduler()
        s.add(0, 5)
        s.add(0, 5)
        self.assertEqual(s.max_disjoint_count(), 1)


class TestCounters(unittest.TestCase):
    def test_subsets_is_power_of_two(self):
        s = demo_input()
        s.max_disjoint_count()
        self.assertEqual(s.count_subsets(), 8)

    def test_overlap_checks_grow(self):
        s = demo_input()
        before = s.count_overlap_checks()
        s.max_disjoint_count()
        self.assertGreater(s.count_overlap_checks(), before)

    def test_weight_sums_grow(self):
        s = demo_input()
        before = s.count_weight_sums()
        s.max_weighted_value()
        self.assertGreater(s.count_weight_sums(), before)

    def test_cost_report_keys(self):
        s = demo_input()
        self.assertEqual(
            sorted(s.cost_report()),
            ["overlap_checks", "subsets", "weight_sums"],
        )


class TestDeterminism(unittest.TestCase):
    def test_repeat_same_sequence(self):
        first = demo_input()
        second = demo_input()
        self.assertEqual(first.best_disjoint_selection(), second.best_disjoint_selection())
        self.assertEqual(first.max_weighted_value(), second.max_weighted_value())
        self.assertEqual(first.count_overlap_checks(), second.count_overlap_checks())

    def test_result_stable_on_repeat(self):
        s = demo_input()
        self.assertEqual(s.best_disjoint_selection(), s.best_disjoint_selection())


if __name__ == "__main__":
    unittest.main()
