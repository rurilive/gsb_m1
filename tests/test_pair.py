"""基线测试：锁住改造前 BrutePair 的现状行为。

这些用例描述的是当前"回溯枚举"实现对外可见的事实，改造后必须继续成立，
因此本文件一字不得修改。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from matchingx.pair import (
    BrutePair,
    MatchingError,
    NotMatchedError,
    UnknownPointError,
)


class TestAddEdge(unittest.TestCase):
    def test_empty_graph(self):
        bp = BrutePair()
        self.assertEqual(bp.left_points, [])
        self.assertEqual(bp.right_points, [])
        self.assertEqual(bp.edge_count(), 0)

    def test_add_edge_registers_points(self):
        bp = BrutePair()
        bp.add_edge("l1", "r1")
        self.assertEqual(bp.left_points, ["l1"])
        self.assertEqual(bp.right_points, ["r1"])
        self.assertEqual(bp.edge_count(), 1)

    def test_add_edge_is_chainable(self):
        bp = BrutePair()
        bp.add_edge("l1", "r1").add_edge("l1", "r2")
        self.assertEqual(bp.edge_count(), 2)
        self.assertEqual(bp.neighbors("l1"), {"r1", "r2"})

    def test_duplicate_edge_counted_once(self):
        bp = BrutePair()
        bp.add_edge("l1", "r1")
        bp.add_edge("l1", "r1")
        self.assertEqual(bp.edge_count(), 1)

    def test_neighbors_unknown_point_raises(self):
        bp = BrutePair()
        with self.assertRaises(UnknownPointError):
            bp.neighbors("nope")


class TestMaxPairs(unittest.TestCase):
    def test_no_edges_has_zero_pairs(self):
        bp = BrutePair()
        bp.add_edge("l1", "r1")
        bp.add_edge("l1", "r1")
        empty = BrutePair()
        self.assertEqual(empty.max_pairs(), 0)
        self.assertEqual(bp.max_pairs(), 1)

    def test_single_edge(self):
        bp = BrutePair()
        bp.add_edge("l1", "r1")
        self.assertEqual(bp.max_pairs(), 1)

    def test_left_and_right_same_size_full(self):
        bp = BrutePair()
        bp.add_edge("l1", "r1")
        bp.add_edge("l2", "r2")
        self.assertEqual(bp.max_pairs(), 2)

    def test_competing_lefts_share_one_right(self):
        bp = BrutePair()
        bp.add_edge("l1", "r1")
        bp.add_edge("l2", "r1")
        self.assertEqual(bp.max_pairs(), 1)

    def test_simple_augmenting_case(self):
        # l1-r1、l2-r1、l2-r2：最大匹配应为 2（l1-r1 与 l2-r2）。
        bp = BrutePair()
        bp.add_edge("l1", "r1")
        bp.add_edge("l2", "r1")
        bp.add_edge("l2", "r2")
        self.assertEqual(bp.max_pairs(), 2)


class TestIsPerfect(unittest.TestCase):
    def test_no_left_points_is_perfect(self):
        bp = BrutePair()
        self.assertTrue(bp.is_perfect())

    def test_left_without_edge_is_not_perfect(self):
        bp = BrutePair()
        bp.add_edge("l1", "r1")
        bp.add_edge("l2", "r1")
        self.assertFalse(bp.is_perfect())

    def test_perfect_when_all_left_covered(self):
        bp = BrutePair()
        bp.add_edge("l1", "r1")
        bp.add_edge("l1", "r2")
        bp.add_edge("l2", "r2")
        self.assertTrue(bp.is_perfect())

    def test_more_left_than_right_not_perfect(self):
        bp = BrutePair()
        bp.add_edge("l1", "r1")
        bp.add_edge("l2", "r1")
        bp.add_edge("l3", "r1")
        self.assertFalse(bp.is_perfect())


class TestMatchedTo(unittest.TestCase):
    def test_matched_to_after_perfect_check(self):
        bp = BrutePair()
        bp.add_edge("l1", "r1")
        bp.add_edge("l2", "r2")
        self.assertTrue(bp.is_perfect())
        self.assertEqual(bp.matched_to("l1"), "r1")
        self.assertEqual(bp.matched_to("l2"), "r2")

    def test_matched_to_unknown_point_raises(self):
        bp = BrutePair()
        bp.add_edge("l1", "r1")
        bp.max_pairs()
        with self.assertRaises(UnknownPointError):
            bp.matched_to("ghost")

    def test_matched_to_unmatched_left_raises(self):
        bp = BrutePair()
        bp.add_edge("l1", "r1")
        bp.add_edge("l2", "r1")
        bp.max_pairs()
        with self.assertRaises(NotMatchedError):
            bp.matched_to("l2")

    def test_matched_to_before_search_raises(self):
        bp = BrutePair()
        bp.add_edge("l1", "r1")
        with self.assertRaises(MatchingError):
            bp.matched_to("l1")


class TestErrorsAndDeterminism(unittest.TestCase):
    def test_errors_share_base_class(self):
        self.assertTrue(issubclass(UnknownPointError, MatchingError))
        self.assertTrue(issubclass(NotMatchedError, MatchingError))

    def test_add_edge_none_raises(self):
        bp = BrutePair()
        with self.assertRaises(UnknownPointError):
            bp.add_edge(None, "r1")

    def test_fixed_graph_repeatable(self):
        def run():
            bp = BrutePair()
            bp.add_edge("l1", "r1")
            bp.add_edge("l1", "r2")
            bp.add_edge("l2", "r1")
            bp.add_edge("l3", "r2")
            return bp.max_pairs(), sorted(bp.left_points), sorted(bp.right_points)

        self.assertEqual(run(), run())


if __name__ == "__main__":
    unittest.main()
