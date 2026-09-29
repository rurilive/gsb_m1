"""基线行为测试：锁住 FlatNet 的朴素遍历能力。"""

import unittest

from graphx.net import FlatNet, GraphError, UnknownNode


class FlatNetTest(unittest.TestCase):
    def _diamond(self):
        g = FlatNet()
        g.add_edge("s", "a", 3)
        g.add_edge("s", "b", 2)
        g.add_edge("a", "t", 1)
        g.add_edge("b", "t", 4)
        return g

    def test_add_edge_registers_both_endpoints(self):
        g = FlatNet()
        g.add_edge("s", "x", 1)
        self.assertTrue(g.has_node("s"))
        self.assertTrue(g.has_node("x"))
        self.assertEqual(g.node_count(), 2)
        self.assertFalse(g.has_node("y"))

    def test_add_node_is_idempotent(self):
        g = FlatNet()
        g.add_node("a")
        g.add_node("a")
        self.assertEqual(g.nodes(), ["a"])
        self.assertEqual(g.node_count(), 1)

    def test_rejects_empty_node_name(self):
        g = FlatNet()
        with self.assertRaises(GraphError):
            g.add_node("")

    def test_rejects_non_numeric_capacity(self):
        g = FlatNet()
        with self.assertRaises(GraphError):
            g.add_edge("a", "b", "big")

    def test_edge_count_and_edges(self):
        g = self._diamond()
        self.assertEqual(g.edge_count(), 4)
        self.assertEqual(
            g.edges(),
            [("s", "a", 3), ("s", "b", 2), ("a", "t", 1), ("b", "t", 4)],
        )

    def test_node_count(self):
        g = self._diamond()
        self.assertEqual(g.node_count(), 4)

    def test_duplicate_edge_is_recorded_twice(self):
        g = FlatNet()
        g.add_edge("s", "t", 5)
        g.add_edge("s", "t", 5)
        self.assertEqual(g.edge_count(), 2)
        self.assertEqual(g.neighbors("s"), [("t", 5), ("t", 5)])

    def test_neighbors_returns_out_edges_in_order(self):
        g = self._diamond()
        self.assertEqual(g.neighbors("s"), [("a", 3), ("b", 2)])

    def test_neighbors_unknown_node(self):
        g = self._diamond()
        with self.assertRaises(UnknownNode):
            g.neighbors("z")

    def test_out_degree(self):
        g = self._diamond()
        self.assertEqual(g.out_degree("s"), 2)
        self.assertEqual(g.out_degree("b"), 1)

    def test_reachable_uses_capacity_blind_traversal(self):
        g = FlatNet()
        g.add_edge("s", "t", 0)
        self.assertTrue(g.reachable("s", "t"))

    def test_reachable_true_across_path(self):
        g = self._diamond()
        self.assertTrue(g.reachable("s", "t"))

    def test_reachable_false_when_blocked(self):
        g = FlatNet()
        g.add_edge("s", "a", 1)
        g.add_node("t")
        self.assertFalse(g.reachable("s", "t"))

    def test_reachable_self(self):
        g = self._diamond()
        self.assertTrue(g.reachable("s", "s"))

    def test_reachable_unknown_node(self):
        g = self._diamond()
        with self.assertRaises(UnknownNode):
            g.reachable("s", "z")

    def test_bfs_order_from_source(self):
        g = self._diamond()
        self.assertEqual(g.bfs_order("s"), ["s", "a", "b", "t"])

    def test_bfs_order_starts_at_source(self):
        g = self._diamond()
        self.assertEqual(g.bfs_order("a")[0], "a")

    def test_bfs_stops_before_unreachable(self):
        g = FlatNet()
        g.add_edge("s", "a", 1)
        g.add_node("z")
        self.assertEqual(g.bfs_order("s"), ["s", "a"])

    def test_bfs_unknown_node(self):
        g = self._diamond()
        with self.assertRaises(UnknownNode):
            g.bfs_order("z")

    def test_graph_error_is_base(self):
        self.assertTrue(issubclass(UnknownNode, GraphError))


if __name__ == "__main__":
    unittest.main()
