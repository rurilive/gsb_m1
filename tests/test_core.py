"""matroid 现状行为的锁定测试。"""

import unittest

from matroid.core import (
    Element,
    Erro,
    Interval,
    Task,
    fractional_knapsack,
    integer_knapsack,
    is_independent,
    max_non_overlapping,
    max_profit_schedule,
    max_weight_basis,
    max_weight_independent,
)


def labels(sub):
    return sorted(x.label for x in sub)


class TestConstruction(unittest.TestCase):
    def test_element_rejects_bad_size(self):
        with self.assertRaises(Erro):
            Element("a", size=-1)
        with self.assertRaises(Erro):
            Element("", size=0)

    def test_interval_rejects_reversed(self):
        with self.assertRaises(Erro):
            Interval(5, 2)

    def test_task_rejects_bad_deadline(self):
        with self.assertRaises(Erro):
            Task("a", duration=1, deadline=0)

    def test_error_base_is_value_error(self):
        self.assertTrue(issubclass(Erro, ValueError))
        with self.assertRaises(Erro):
            Element(None)


class TestIndependence(unittest.TestCase):
    def test_partition_style_subset_is_independent(self):
        elems = [Element("a", size=1), Element("b", size=2), Element("c", size=3)]
        self.assertTrue(is_independent(elems, elems))

    def test_duplicate_size_is_not_independent(self):
        elems = [Element("a", size=1), Element("b", size=1)]
        self.assertFalse(is_independent(elems, elems))

    def test_unknown_label_raises(self):
        elems = [Element("a", size=1)]
        with self.assertRaises(Erro):
            is_independent(elems, [Element("ghost", size=9)])

    def test_empty_subset_is_independent(self):
        elems = [Element("a", size=1)]
        self.assertTrue(is_independent(elems, []))


class TestMaxWeightIndependent(unittest.TestCase):
    def test_picks_highest_weight(self):
        elems = [
            Element("a", size=1, weight=3),
            Element("b", size=2, weight=5),
            Element("c", size=3, weight=4),
        ]
        self.assertEqual(labels(max_weight_independent(elems)), ["a", "b", "c"])

    def test_conflicting_sizes_choose_best_pair(self):
        elems = [
            Element("a", size=1, weight=10),
            Element("b", size=1, weight=4),
            Element("c", size=2, weight=6),
        ]
        self.assertEqual(labels(max_weight_independent(elems)), ["a", "c"])

    def test_empty_ground_set(self):
        self.assertEqual(max_weight_independent([]), [])

    def test_deterministic(self):
        elems = [Element("a", size=1, weight=2), Element("b", size=2, weight=2)]
        self.assertEqual(
            labels(max_weight_independent(elems)),
            labels(max_weight_independent(elems)),
        )


class TestMaxWeightBasis(unittest.TestCase):
    def test_basis_is_largest_independent_set(self):
        elems = [
            Element("a", size=1, weight=1),
            Element("b", size=2, weight=1),
            Element("c", size=3, weight=9),
        ]
        self.assertEqual(labels(max_weight_basis(elems)), ["a", "b", "c"])

    def test_basis_empty(self):
        self.assertEqual(max_weight_basis([]), [])


class TestNonOverlapping(unittest.TestCase):
    def test_counts_intervals(self):
        ivs = [Interval(1, 3), Interval(2, 4), Interval(5, 7)]
        self.assertEqual(len(max_non_overlapping(ivs)), 2)

    def test_empty(self):
        self.assertEqual(max_non_overlapping([]), [])

    def test_all_overlap(self):
        ivs = [Interval(1, 10), Interval(2, 5), Interval(4, 6)]
        chosen = max_non_overlapping(ivs)
        self.assertEqual(len(chosen), 1)

    def test_deterministic(self):
        ivs = [Interval(1, 2), Interval(2, 3), Interval(1, 3)]
        first = max_non_overlapping(ivs)
        second = max_non_overlapping(ivs)
        self.assertEqual(
            [(v.start, v.end) for v in first],
            [(v.start, v.end) for v in second],
        )


class TestKnapsack(unittest.TestCase):
    def test_fractional_beats_integer_when_divisible(self):
        elems = [Element("a", size=2, weight=3), Element("b", size=1, weight=1)]
        f_value, _ = fractional_knapsack(elems, 2)
        i_value, _ = integer_knapsack(elems, 2)
        self.assertEqual(f_value, 3)
        self.assertEqual(i_value, 3)

    def test_integer_knapsack_picks_by_capacity(self):
        elems = [
            Element("a", size=3, weight=5),
            Element("b", size=2, weight=4),
            Element("c", size=1, weight=1),
        ]
        value, sub = integer_knapsack(elems, 3)
        self.assertEqual(value, 5)
        self.assertEqual(labels(sub), ["a"])

    def test_zero_capacity(self):
        elems = [Element("a", size=1, weight=5)]
        self.assertEqual(fractional_knapsack(elems, 0)[0], 0)
        self.assertEqual(integer_knapsack(elems, 0)[0], 0)

    def test_negative_capacity_raises(self):
        with self.assertRaises(Erro):
            fractional_knapsack([], -1)

    def test_empty_items(self):
        self.assertEqual(fractional_knapsack([], 5)[0], 0)
        self.assertEqual(integer_knapsack([], 5)[0], 0)


class TestSchedule(unittest.TestCase):
    def test_picks_profitable_feasible_tasks(self):
        tasks = [
            Task("a", duration=1, deadline=1, weight=5),
            Task("b", duration=1, deadline=1, weight=4),
            Task("c", duration=1, deadline=2, weight=6),
        ]
        self.assertEqual(labels(max_profit_schedule(tasks)), ["a", "c"])

    def test_all_conflict_keeps_best(self):
        tasks = [
            Task("a", duration=2, deadline=2, weight=3),
            Task("b", duration=3, deadline=3, weight=1),
        ]
        self.assertEqual(labels(max_profit_schedule(tasks)), ["a"])

    def test_empty(self):
        self.assertEqual(max_profit_schedule([]), [])

    def test_deterministic(self):
        tasks = [Task("a", duration=1, deadline=2, weight=2)]
        first = labels(max_profit_schedule(tasks))
        second = labels(max_profit_schedule(tasks))
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
