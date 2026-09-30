"""基线测试：锁住改造前 ReachGraph 的现状行为。

这些用例描述的是当前"两两可达判断"实现对外可见的事实，改造后必须继续
成立，因此本文件一字不得修改。测试只覆盖基线已有的接口，不涉及任何
分量级的新能力。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sccdag.graph import (
    GraphError,
    ReachGraph,
    SccError,
    UnknownNodeError,
)


def make_graph(nodes, edges):
    """按给定节点与边构造一张图，节点按顺序加入以固定遍历次序。"""
    g = ReachGraph()
    for n in nodes:
        g.add_node(n)
    for u, v in edges:
        g.add_edge(u, v)
    return g


class TestConstruction(unittest.TestCase):
    def test_empty_graph(self):
        g = ReachGraph()
        self.assertEqual(g.size(), 0)
        self.assertEqual(g.edge_count(), 0)
        self.assertEqual(g.nodes(), [])
        self.assertEqual(g.edges(), [])

    def test_add_node_is_idempotent(self):
        g = ReachGraph()
        g.add_node("a")
        g.add_node("b")
        g.add_edge("a", "b")
        g.add_node("a")
        self.assertEqual(g.size(), 2)
        self.assertEqual(g.neighbors("a"), ["b"])

    def test_add_edge_requires_endpoints(self):
        g = ReachGraph()
        g.add_node("a")
        with self.assertRaises(UnknownNodeError):
            g.add_edge("a", "b")
        with self.assertRaises(UnknownNodeError):
            g.add_edge("x", "a")

    def test_nodes_keep_insertion_order(self):
        g = make_graph(["a", "b", "c"], [])
        self.assertEqual(g.nodes(), ["a", "b", "c"])

    def test_edges_keep_insertion_order(self):
        g = make_graph(["a", "b", "c"], [("a", "b"), ("a", "c"), ("b", "c")])
        self.assertEqual(g.edges(), [("a", "b"), ("a", "c"), ("b", "c")])


class TestNeighborsAndDegree(unittest.TestCase):
    def test_neighbors_are_copy(self):
        g = make_graph(["a", "b"], [("a", "b")])
        nbrs = g.neighbors("a")
        nbrs.append("b")
        self.assertEqual(g.neighbors("a"), ["b"])

    def test_degree_counts_edges(self):
        g = make_graph(["a", "b", "c"], [("a", "b"), ("a", "c"), ("a", "b")])
        self.assertEqual(g.degree("a"), 3)
        self.assertEqual(g.degree("b"), 0)

    def test_self_loop_counted(self):
        g = make_graph(["a"], [("a", "a")])
        self.assertEqual(g.degree("a"), 1)
        self.assertEqual(g.edge_count(), 1)

    def test_unknown_node_raises(self):
        g = ReachGraph()
        with self.assertRaises(UnknownNodeError):
            g.neighbors("z")
        with self.assertRaises(UnknownNodeError):
            g.degree("z")


class TestReachable(unittest.TestCase):
    def test_reflexive(self):
        g = make_graph(["a"], [])
        self.assertTrue(g.reachable("a", "a"))

    def test_direct_edge(self):
        g = make_graph(["a", "b"], [("a", "b")])
        self.assertTrue(g.reachable("a", "b"))
        self.assertFalse(g.reachable("b", "a"))

    def test_indirect_path(self):
        g = make_graph(["a", "b", "c"], [("a", "b"), ("b", "c")])
        self.assertTrue(g.reachable("a", "c"))
        self.assertFalse(g.reachable("c", "a"))

    def test_unreachable_branches(self):
        g = make_graph(["a", "b", "c", "d"], [("a", "b"), ("c", "d")])
        self.assertFalse(g.reachable("a", "d"))
        self.assertFalse(g.reachable("b", "a"))

    def test_missing_endpoint_raises(self):
        g = make_graph(["a"], [])
        with self.assertRaises(UnknownNodeError):
            g.reachable("a", "z")
        with self.assertRaises(UnknownNodeError):
            g.reachable("z", "a")


class TestMutual(unittest.TestCase):
    def test_cycle_is_mutual(self):
        g = make_graph(["a", "b", "c"], [("a", "b"), ("b", "c"), ("c", "a")])
        self.assertTrue(g.same_component("a", "c"))
        self.assertTrue(g.same_component("c", "b"))
        self.assertTrue(g.bidirectional("a", "b"))

    def test_chain_not_mutual(self):
        g = make_graph(["a", "b", "c"], [("a", "b"), ("b", "c")])
        self.assertFalse(g.same_component("a", "c"))
        self.assertTrue(g.reachable("a", "c"))
        self.assertFalse(g.bidirectional("a", "c"))

    def test_self_is_same_component(self):
        g = make_graph(["a", "b"], [])
        self.assertTrue(g.same_component("a", "a"))
        self.assertTrue(g.bidirectional("a", "a"))

    def test_two_cycles_disjoint(self):
        g = make_graph(
            ["a", "b", "c", "d"],
            [("a", "b"), ("b", "a"), ("c", "d"), ("d", "c")],
        )
        self.assertTrue(g.same_component("a", "b"))
        self.assertTrue(g.same_component("c", "d"))
        self.assertFalse(g.same_component("a", "c"))


class TestExceptions(unittest.TestCase):
    def test_hierarchy(self):
        self.assertTrue(issubclass(UnknownNodeError, SccError))
        self.assertTrue(issubclass(GraphError, SccError))
        self.assertTrue(issubclass(SccError, Exception))


class TestDeterminism(unittest.TestCase):
    def test_edges_stable_across_builds(self):
        g1 = make_graph(["a", "b", "c"], [("a", "b"), ("a", "c"), ("b", "c")])
        g2 = make_graph(["a", "b", "c"], [("a", "b"), ("a", "c"), ("b", "c")])
        self.assertEqual(g1.edges(), g2.edges())
        self.assertEqual(g1.neighbors("a"), g2.neighbors("a"))
        self.assertEqual(g1.degree("a"), g2.degree("a"))


if __name__ == "__main__":
    unittest.main()
