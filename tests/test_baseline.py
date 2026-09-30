"""基线测试：锁住改造前 GraphMatcher 的现状行为。

这些用例描述的是当前回溯枚举实现对外可见的事实，改造成带花树之后
必须继续成立，因此本文件一字不得修改。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from blossom.matching import (
    GraphError,
    GraphMatcher,
    MatchError,
    NodeError,
    NotMatchedError,
)


def build(edges):
    m = GraphMatcher()
    for u, v in edges:
        m.add_edge(u, v)
    return m


class TestBuild(unittest.TestCase):
    def test_empty_graph(self):
        m = GraphMatcher()
        self.assertEqual(m.nodes, [])
        self.assertEqual(m.node_count(), 0)
        self.assertEqual(m.edge_count(), 0)

    def test_add_edge_registers_points(self):
        m = GraphMatcher()
        m.add_edge("a", "b")
        self.assertEqual(m.nodes, ["a", "b"])
        self.assertEqual(m.node_count(), 2)
        self.assertEqual(m.edge_count(), 1)

    def test_add_edge_is_chainable(self):
        m = GraphMatcher()
        m.add_edge("a", "b").add_edge("a", "c")
        self.assertEqual(m.edge_count(), 2)
        self.assertEqual(m.neighbors("a"), {"b", "c"})

    def test_duplicate_edge_counted_once(self):
        m = GraphMatcher()
        m.add_edge("a", "b")
        m.add_edge("b", "a")
        self.assertEqual(m.edge_count(), 1)
        self.assertEqual(m.edges(), [("a", "b")])

    def test_edges_sorted_stable(self):
        m = build([("c", "d"), ("a", "c"), ("a", "b")])
        self.assertEqual(m.edges(), [("a", "b"), ("a", "c"), ("c", "d")])

    def test_self_loop_rejected(self):
        m = GraphMatcher()
        with self.assertRaises(GraphError):
            m.add_edge("a", "a")

    def test_none_endpoint_rejected(self):
        m = GraphMatcher()
        with self.assertRaises(GraphError):
            m.add_edge("a", None)

    def test_neighbors_unknown_point_raises(self):
        m = GraphMatcher()
        with self.assertRaises(NodeError):
            m.neighbors("x")

    def test_has_edge_unknown_point_raises(self):
        m = build([("a", "b")])
        with self.assertRaises(NodeError):
            m.has_edge("a", "z")

    def test_has_edge_true_and_false(self):
        m = build([("a", "b"), ("b", "c")])
        self.assertTrue(m.has_edge("b", "a"))
        self.assertFalse(m.has_edge("a", "c"))


class TestSingleAndTwoPoint(unittest.TestCase):
    def test_empty_graph_has_no_matching(self):
        self.assertEqual(build([]).max_matching_size(), 0)
        self.assertTrue(build([]).perfect_matching_exists())

    def test_two_points_with_edge(self):
        m = build([("a", "b")])
        self.assertEqual(m.max_matching_size(), 1)
        self.assertTrue(m.perfect_matching_exists())
        self.assertEqual(m.max_matching(), {"a": "b", "b": "a"})

    def test_two_points_without_edge(self):
        # a、b 都在图里，但两者之间没有边，各自只连着别的点。
        m = build([("a", "c"), ("b", "d")])
        self.assertFalse(m.has_edge("a", "b"))
        self.assertEqual(m.max_matching_size(), 2)


class TestOddCyclesAndComplete(unittest.TestCase):
    def test_triangle_takes_one(self):
        m = build([("a", "b"), ("a", "c"), ("b", "c")])
        self.assertEqual(m.max_matching_size(), 1)
        self.assertFalse(m.perfect_matching_exists())

    def test_five_cycle_takes_two(self):
        m = build([("1", "2"), ("2", "3"), ("3", "4"), ("4", "5"), ("5", "1")])
        self.assertEqual(m.max_matching_size(), 2)
        self.assertFalse(m.perfect_matching_exists())

    def test_complete_graph_four(self):
        m = build(
            [
                ("a", "b"),
                ("a", "c"),
                ("a", "d"),
                ("b", "c"),
                ("b", "d"),
                ("c", "d"),
            ]
        )
        self.assertEqual(m.max_matching_size(), 2)
        self.assertTrue(m.perfect_matching_exists())

    def test_star_takes_one(self):
        m = build([("a", "b"), ("a", "c")])
        self.assertEqual(m.max_matching_size(), 1)

    def test_odd_cycle_inside_bigger_graph(self):
        m = build(
            [
                ("a", "b"),
                ("b", "c"),
                ("c", "a"),
                ("c", "d"),
                ("d", "e"),
                ("e", "c"),
            ]
        )
        self.assertEqual(m.max_matching_size(), 2)


class TestDisconnected(unittest.TestCase):
    def test_two_disjoint_edges(self):
        m = build([("a", "b"), ("c", "d")])
        self.assertEqual(m.max_matching_size(), 2)
        self.assertTrue(m.perfect_matching_exists())

    def test_isolated_component_limits_cover(self):
        m = build([("a", "b"), ("c", "d"), ("d", "e")])
        self.assertEqual(m.max_matching_size(), 2)
        self.assertFalse(m.perfect_matching_exists())

    def test_path_and_edge(self):
        m = build([("a", "b"), ("b", "c"), ("x", "y")])
        self.assertEqual(m.max_matching_size(), 2)
        self.assertFalse(m.perfect_matching_exists())


class TestMaximumCheck(unittest.TestCase):
    def test_is_maximum_true_for_largest(self):
        m = build([("a", "b"), ("a", "c"), ("b", "c")])
        self.assertTrue(m.is_maximum({"a": "b", "b": "a"}))

    def test_is_maximum_false_for_smaller(self):
        m = build([("a", "b"), ("a", "c"), ("b", "c")])
        self.assertFalse(m.is_maximum({}))

    def test_is_maximum_rejects_bad_point(self):
        m = build([("a", "b")])
        with self.assertRaises(NodeError):
            m.is_maximum({"a": "z", "z": "a"})

    def test_is_maximum_rejects_non_edge(self):
        m = build([("a", "b"), ("c", "d")])
        with self.assertRaises(MatchError):
            m.is_maximum({"a": "c", "c": "a"})

    def test_is_maximum_rejects_shared_point(self):
        m = build([("a", "b"), ("c", "b")])
        with self.assertRaises(MatchError):
            m.is_maximum({"a": "b", "c": "b"})

    def test_is_maximum_rejects_none(self):
        m = build([("a", "b")])
        with self.assertRaises(MatchError):
            m.is_maximum(None)


class TestPlanAndLookup(unittest.TestCase):
    def test_plan_size_matches(self):
        m = build([("a", "b"), ("a", "c"), ("b", "c"), ("c", "d")])
        plan = m.max_matching()
        self.assertEqual(len(plan) // 2, m.max_matching_size())

    def test_plan_is_legal_matching(self):
        m = build([("a", "b"), ("a", "c"), ("b", "c"), ("c", "d")])
        plan = m.max_matching()
        for u, v in plan.items():
            self.assertEqual(plan[v], u)
            self.assertTrue(m.has_edge(u, v))
        self.assertEqual(len(set(plan)), len(plan))

    def test_matched_to_unknown_point_raises(self):
        m = build([("a", "b")])
        with self.assertRaises(NodeError):
            m.matched_to("z")

    def test_matched_to_unmatched_point_raises(self):
        m = build([("a", "b"), ("a", "c")])
        self.assertEqual(m.matched_to("a"), "b")
        with self.assertRaises(NotMatchedError):
            m.matched_to("c")

    def test_matched_to_is_symmetric(self):
        m = build([("a", "b"), ("c", "d")])
        self.assertEqual(m.matched_to("a"), "b")
        self.assertEqual(m.matched_to("b"), "a")

    def test_repeated_calls_are_stable(self):
        m = build([("a", "b"), ("a", "c"), ("b", "c"), ("c", "d")])
        first = m.max_matching()
        second = m.max_matching()
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
