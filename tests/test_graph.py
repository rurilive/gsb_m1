"""bridgecut 现有行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from bridgecut.graph import (
    UndirectedGraph,
    GraphError,
    InvalidGraphError,
    NodeNotFoundError,
)


def two_triangles():
    # 三角形 0-1-2，桥 2-3，再一个三角形 3-4-5。
    edges = [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 5), (5, 3)]
    return UndirectedGraph(6, edges)


class TestBasics(unittest.TestCase):
    def test_counts(self):
        g = two_triangles()
        self.assertEqual(g.node_count(), 6)
        self.assertEqual(g.edge_count(), 7)

    def test_nodes_edges(self):
        g = two_triangles()
        self.assertEqual(g.nodes(), [0, 1, 2, 3, 4, 5])
        self.assertEqual(g.edges()[3], (2, 3))

    def test_connected(self):
        g = two_triangles()
        self.assertTrue(g.is_connected())
        self.assertTrue(g.connected(0, 5))
        self.assertTrue(g.connected(1, 1))


class TestBridgesAndPoints(unittest.TestCase):
    def test_bridges_ordered(self):
        self.assertEqual(two_triangles().bridges(), [3])

    def test_articulation_points(self):
        self.assertEqual(two_triangles().articulation_points(), [2, 3])

    def test_two_node_edge(self):
        g = UndirectedGraph(2, [(0, 1)])
        self.assertEqual(g.bridges(), [0])
        self.assertEqual(g.articulation_points(), [])

    def test_tree_all_edges_bridges(self):
        g = UndirectedGraph(4, [(0, 1), (1, 2), (2, 3)])
        self.assertEqual(g.bridges(), [0, 1, 2])
        self.assertEqual(g.articulation_points(), [1, 2])

    def test_cycle_no_bridge(self):
        g = UndirectedGraph(3, [(0, 1), (1, 2), (2, 0)])
        self.assertEqual(g.bridges(), [])
        self.assertEqual(g.articulation_points(), [])

    def test_self_loop(self):
        g = UndirectedGraph(1, [(0, 0)])
        self.assertEqual(g.bridges(), [])
        self.assertEqual(g.articulation_points(), [])

    def test_multi_edge_no_bridge(self):
        g = UndirectedGraph(2, [(0, 1), (0, 1)])
        self.assertEqual(g.bridges(), [])
        self.assertEqual(g.articulation_points(), [])


class TestComponents(unittest.TestCase):
    def test_edge_components(self):
        self.assertEqual(two_triangles().edge_components(), [[0, 1, 2], [3], [4, 5, 6]])

    def test_vertex_components(self):
        self.assertEqual(two_triangles().vertex_components(), [[0, 1, 2], [3, 4, 5]])

    def test_bridge_tree(self):
        tree = two_triangles().bridge_tree()
        self.assertEqual(tree["components"], [[0, 1, 2], [3, 4, 5]])
        self.assertEqual(tree["bridges"], [(0, 1, 3)])

    def test_empty_graph(self):
        g = UndirectedGraph(1, [])
        self.assertEqual(g.bridges(), [])
        self.assertEqual(g.edge_components(), [])
        self.assertEqual(g.vertex_components(), [[0]])

    def test_multiple_components(self):
        g = UndirectedGraph(4, [(0, 1), (2, 3)])
        self.assertFalse(g.is_connected())
        self.assertEqual(g.bridges(), [0, 1])
        self.assertEqual(g.vertex_components(), [[0], [1], [2], [3]])

    def test_repeat_run_equal(self):
        g = two_triangles()
        self.assertEqual(g.bridges(), g.bridges())
        self.assertEqual(g.edge_components(), g.edge_components())


class TestMustPass(unittest.TestCase):
    def test_must_pass_edge_true(self):
        self.assertTrue(two_triangles().must_pass_edge(0, 4, 3))

    def test_must_pass_edge_false(self):
        self.assertFalse(two_triangles().must_pass_edge(0, 1, 0))

    def test_must_pass_node_true(self):
        self.assertTrue(two_triangles().must_pass_node(0, 4, 2))

    def test_must_pass_node_false(self):
        self.assertFalse(two_triangles().must_pass_node(1, 2, 0))


class TestCounters(unittest.TestCase):
    def test_counters_after_bridges(self):
        g = two_triangles()
        g.reset_counters()
        g.bridges()
        c = g.counters()
        self.assertEqual(c["connectivity_checks"], 1 + g.edge_count())
        self.assertGreater(c["edge_visits"], 0)

    def test_counters_reset(self):
        g = two_triangles()
        g.bridges()
        g.reset_counters()
        self.assertEqual(g.counters(), {"connectivity_checks": 0, "edge_visits": 0})


class TestErrors(unittest.TestCase):
    def test_single_node(self):
        g = UndirectedGraph(1, [])
        self.assertEqual(g.bridges(), [])
        self.assertEqual(g.articulation_points(), [])

    def test_errors_share_base(self):
        self.assertTrue(issubclass(InvalidGraphError, GraphError))
        self.assertTrue(issubclass(NodeNotFoundError, GraphError))

    def test_zero_nodes_rejected(self):
        with self.assertRaises(InvalidGraphError):
            UndirectedGraph(0, [])

    def test_non_list_edges_rejected(self):
        with self.assertRaises(InvalidGraphError):
            UndirectedGraph(3, "abc")

    def test_bad_edge_shape_rejected(self):
        with self.assertRaises(InvalidGraphError):
            UndirectedGraph(3, [(0, 1, 2)])

    def test_endpoint_out_of_range(self):
        with self.assertRaises(InvalidGraphError):
            UndirectedGraph(3, [(0, 9)])

    def test_bad_edge_index(self):
        with self.assertRaises(InvalidGraphError):
            two_triangles().must_pass_edge(0, 4, 99)

    def test_unknown_node(self):
        with self.assertRaises(NodeNotFoundError):
            two_triangles().must_pass_node(0, 4, 99)


if __name__ == "__main__":
    unittest.main()
