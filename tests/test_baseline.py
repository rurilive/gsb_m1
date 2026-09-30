"""基线测试：锁住改造前 PathCoverer 的现状行为。

这些用例描述的是当前枚举顶点划分实现对外可见的事实，改造成拆点建
二分图求最大匹配之后必须继续成立，因此本文件一字不得修改。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathcover.covering import (
    CoverError,
    GraphError,
    NodeError,
    PathCoverer,
)


def build(edges):
    g = PathCoverer()
    for u, v in edges:
        g.add_edge(u, v)
    return g


class TestBuild(unittest.TestCase):
    def test_empty_graph(self):
        g = PathCoverer()
        self.assertEqual(g.nodes, [])
        self.assertEqual(g.node_count(), 0)
        self.assertEqual(g.edge_count(), 0)

    def test_add_edge_registers_points(self):
        g = PathCoverer()
        g.add_edge("a", "b")
        self.assertEqual(g.nodes, ["a", "b"])
        self.assertEqual(g.node_count(), 2)
        self.assertEqual(g.edge_count(), 1)

    def test_add_edge_is_chainable(self):
        g = PathCoverer()
        g.add_edge("a", "b").add_edge("a", "c")
        self.assertEqual(g.edge_count(), 2)
        self.assertEqual(g.successors("a"), {"b", "c"})

    def test_add_node_registers_isolated(self):
        g = PathCoverer()
        g.add_node("z")
        self.assertEqual(g.nodes, ["z"])
        self.assertEqual(g.successors("z"), set())

    def test_duplicate_edge_counted_once(self):
        g = PathCoverer()
        g.add_edge("a", "b")
        g.add_edge("a", "b")
        self.assertEqual(g.edge_count(), 1)
        self.assertEqual(g.edges(), [("a", "b")])

    def test_reverse_edge_is_distinct(self):
        g = PathCoverer()
        g.add_edge("a", "b")
        g.add_edge("b", "a")
        self.assertEqual(g.edge_count(), 2)

    def test_edges_sorted_stable(self):
        g = build([("c", "d"), ("a", "c"), ("a", "b")])
        self.assertEqual(g.edges(), [("a", "b"), ("a", "c"), ("c", "d")])

    def test_self_loop_rejected(self):
        g = PathCoverer()
        with self.assertRaises(GraphError):
            g.add_edge("a", "a")

    def test_none_endpoint_rejected(self):
        g = PathCoverer()
        with self.assertRaises(GraphError):
            g.add_edge("a", None)

    def test_successors_unknown_point_raises(self):
        g = PathCoverer()
        with self.assertRaises(NodeError):
            g.successors("x")

    def test_has_edge_unknown_point_raises(self):
        g = build([("a", "b")])
        with self.assertRaises(NodeError):
            g.has_edge("a", "z")

    def test_has_edge_true_and_false(self):
        g = build([("a", "b"), ("b", "c")])
        self.assertTrue(g.has_edge("a", "b"))
        self.assertFalse(g.has_edge("b", "a"))


class TestSingleAndTwoPoint(unittest.TestCase):
    def test_empty_graph_has_no_paths(self):
        self.assertEqual(build([]).min_path_count(), 0)

    def test_single_point_needs_one_path(self):
        g = PathCoverer()
        g.add_node("a")
        self.assertEqual(g.min_path_count(), 1)
        self.assertEqual(g.min_path_cover(), [["a"]])

    def test_two_points_with_edge(self):
        g = build([("a", "b")])
        self.assertEqual(g.min_path_count(), 1)
        self.assertEqual(g.min_path_cover(), [["a", "b"]])

    def test_two_points_without_edge(self):
        g = build([("a", "c"), ("b", "d")])
        self.assertFalse(g.has_edge("a", "b"))
        self.assertEqual(g.min_path_count(), 2)


class TestChainsAndBranches(unittest.TestCase):
    def test_single_chain(self):
        g = build([("a", "b"), ("b", "c"), ("c", "d")])
        self.assertEqual(g.min_path_count(), 1)
        self.assertEqual(g.min_path_cover(), [["a", "b", "c", "d"]])

    def test_two_chains(self):
        g = build([("1", "2"), ("3", "4")])
        self.assertEqual(g.min_path_count(), 2)

    def test_branch_needs_two_paths(self):
        # a 同时指向 b 与 c，b、c 之后都没有出边，一条路径盖不住两点。
        g = build([("a", "b"), ("a", "c")])
        self.assertEqual(g.min_path_count(), 2)

    def test_two_step_branch(self):
        g = build([("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")])
        self.assertEqual(g.min_path_count(), 2)
        self.assertTrue(g.is_valid_cover(g.min_path_cover()))

    def test_single_isolated_point_plus_chain(self):
        g = build([("a", "b"), ("b", "c")])
        g.add_node("z")
        self.assertEqual(g.min_path_count(), 2)
        self.assertTrue(g.is_valid_cover(g.min_path_cover()))


class TestMergeAndSplit(unittest.TestCase):
    def test_diamond_takes_two(self):
        g = build([("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")])
        self.assertEqual(g.min_path_count(), 2)

    def test_all_isolated(self):
        g = PathCoverer()
        for v in ["a", "b", "c"]:
            g.add_node(v)
        self.assertEqual(g.min_path_count(), 3)

    def test_disconnected_components(self):
        g = build([("a", "b"), ("c", "d"), ("d", "e")])
        self.assertEqual(g.min_path_count(), 2)


class TestPlanAndCheck(unittest.TestCase):
    def test_plan_count_matches(self):
        g = build([("a", "b"), ("a", "c"), ("b", "c"), ("c", "d")])
        plan = g.min_path_cover()
        self.assertEqual(len(plan), g.min_path_count())

    def test_plan_is_legal_cover(self):
        g = build([("a", "b"), ("a", "c"), ("b", "c"), ("c", "d")])
        plan = g.min_path_cover()
        self.assertTrue(g.is_valid_cover(plan))

    def test_is_valid_cover_rejects_missing_point(self):
        g = build([("a", "b"), ("b", "c")])
        with self.assertRaises(CoverError):
            g.is_valid_cover([["a"]])

    def test_is_valid_cover_rejects_repeated_point(self):
        g = build([("a", "b"), ("b", "c")])
        with self.assertRaises(CoverError):
            g.is_valid_cover([["a", "b"], ["b", "c"]])

    def test_is_valid_cover_rejects_non_edge(self):
        g = build([("a", "b"), ("b", "c")])
        with self.assertRaises(CoverError):
            g.is_valid_cover([["a", "c", "b"]])

    def test_is_valid_cover_rejects_unknown_point(self):
        g = build([("a", "b")])
        with self.assertRaises(NodeError):
            g.is_valid_cover([["a", "b"], ["z"]])

    def test_is_valid_cover_rejects_none(self):
        g = build([("a", "b")])
        with self.assertRaises(CoverError):
            g.is_valid_cover(None)

    def test_repeated_calls_are_stable(self):
        g = build([("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")])
        first = g.min_path_cover()
        second = g.min_path_cover()
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
