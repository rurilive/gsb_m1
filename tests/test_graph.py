"""Graph 现有行为的锁定测试（基线，一字不改）。"""

import unittest

from graphx import EmptyGraphError, Graph, GraphxError, UnknownNodeError


def build(pairs, nodes=()):
    graph = Graph()
    for value in nodes:
        graph.add_node(value)
    for u, v in pairs:
        graph.add_edge(u, v)
    return graph


class TestStructure(unittest.TestCase):
    def test_empty_graph(self):
        graph = Graph()
        self.assertEqual(graph.nodes(), [])
        self.assertEqual(graph.edges(), [])
        self.assertEqual(graph.node_count(), 0)
        self.assertEqual(graph.edge_count(), 0)

    def test_add_node_once(self):
        graph = Graph().add_node(1).add_node(1)
        self.assertEqual(graph.nodes(), [1])
        self.assertEqual(graph.node_count(), 1)

    def test_add_edge_chains(self):
        graph = Graph().add_edge(1, 2).add_edge(2, 3)
        self.assertEqual(graph.nodes(), [1, 2, 3])
        self.assertEqual(graph.edges(), [(1, 2), (2, 3)])

    def test_self_loop_kept(self):
        graph = build([(1, 1)])
        self.assertEqual(graph.edges(), [(1, 1)])
        self.assertEqual(graph.out_degree(1), 1)

    def test_parallel_edges_kept(self):
        graph = build([(1, 2), (1, 2)])
        self.assertEqual(graph.edge_count(), 2)
        self.assertEqual(graph.neighbors(1), [2, 2])

    def test_neighbors_order(self):
        graph = build([(1, 2), (1, 3), (2, 3)])
        self.assertEqual(graph.neighbors(1), [2, 3])

    def test_out_degree(self):
        graph = build([(1, 2), (1, 3), (1, 4)])
        self.assertEqual(graph.out_degree(1), 3)
        self.assertEqual(graph.out_degree(2), 0)

    def test_nodes_order_is_insertion_order(self):
        graph = build([(3, 1), (1, 2)])
        self.assertEqual(graph.nodes(), [3, 1, 2])

    def test_has_node(self):
        graph = build([(1, 2)])
        self.assertTrue(graph.has_node(1))
        self.assertFalse(graph.has_node(9))

    def test_no_module_level_state(self):
        first = build([(1, 2)])
        before = first.node_count()
        second = build([(3, 4)])
        self.assertEqual(second.nodes(), [3, 4])
        self.assertEqual(first.node_count(), before)


class TestConnectivity(unittest.TestCase):
    def test_single_node_connected(self):
        graph = build([], nodes=[1])
        self.assertTrue(graph.is_connected())
        self.assertEqual(graph.component_count(), 1)

    def test_chain_is_connected(self):
        graph = build([(1, 2), (2, 3), (3, 4)])
        self.assertTrue(graph.is_connected())
        self.assertEqual(graph.component_count(), 1)

    def test_disconnected_components(self):
        graph = build([(1, 2), (3, 4)])
        self.assertFalse(graph.is_connected())
        self.assertEqual(graph.component_count(), 2)

    def test_isolated_nodes(self):
        graph = build([(1, 2)], nodes=[3, 4])
        self.assertEqual(graph.component_count(), 3)

    def test_reachable_self(self):
        graph = build([(1, 2)])
        self.assertTrue(graph.reachable(1, 1))

    def test_reachable_ignores_direction(self):
        graph = build([(1, 2)])
        self.assertTrue(graph.reachable(2, 1))

    def test_reachable_across_components(self):
        graph = build([(1, 2), (3, 4)])
        self.assertFalse(graph.reachable(1, 3))

    def test_sweep_count_grows(self):
        graph = build([(1, 2), (2, 3)])
        start = graph.sweep_count()
        graph.component_count()
        graph.is_connected()
        self.assertEqual(graph.sweep_count(), start + 2)

    def test_reset_sweep_count(self):
        graph = build([(1, 2)])
        graph.component_count()
        graph.reset_sweep_count()
        self.assertEqual(graph.sweep_count(), 0)


class TestCuts(unittest.TestCase):
    def test_tree_all_internal_split_vertices(self):
        graph = build([(1, 2), (2, 3), (3, 4)])
        self.assertEqual(graph.split_vertices(), [2, 3])

    def test_star_center_is_split_vertex(self):
        graph = build([(1, 2), (1, 3), (1, 4)])
        self.assertEqual(graph.split_vertices(), [1])

    def test_cycle_has_no_split_vertex(self):
        graph = build([(1, 2), (2, 3), (3, 1)])
        self.assertEqual(graph.split_vertices(), [])

    def test_tree_all_edges_are_bridges(self):
        graph = build([(1, 2), (2, 3)])
        self.assertEqual(graph.bridges(), [(1, 2), (2, 3)])

    def test_cycle_has_no_bridge(self):
        graph = build([(1, 2), (2, 3), (3, 1)])
        self.assertEqual(graph.bridges(), [])

    def test_double_edge_is_not_bridge(self):
        graph = build([(1, 2), (1, 2)])
        self.assertEqual(graph.bridges(), [])
        self.assertEqual(graph.bidirectional_edges(), [(1, 2), (1, 2)])

    def test_self_loop_is_not_bridge(self):
        graph = build([(1, 1)])
        self.assertEqual(graph.bridges(), [])

    def test_bidirectional_edges_are_the_rest(self):
        graph = build([(1, 2), (2, 3), (3, 1), (3, 4)])
        self.assertEqual(graph.bridges(), [(3, 4)])
        self.assertEqual(
            graph.bidirectional_edges(), [(1, 2), (2, 3), (3, 1)]
        )


class TestScc(unittest.TestCase):
    def test_single_node_scc(self):
        graph = build([], nodes=[1])
        self.assertEqual(graph.scc(), [[1]])

    def test_cycle_is_one_scc(self):
        graph = build([(1, 2), (2, 3), (3, 1)])
        self.assertEqual(graph.scc(), [[1, 2, 3]])

    def test_self_loop_is_one_scc(self):
        graph = build([(1, 1), (1, 2)])
        self.assertEqual(graph.scc(), [[1], [2]])

    def test_chain_sccs_are_singletons(self):
        graph = build([(1, 2), (2, 3)])
        self.assertEqual(graph.scc(), [[1], [2], [3]])

    def test_disconnected_sccs(self):
        graph = build([(1, 2), (2, 1), (3, 4), (4, 3)])
        self.assertEqual(graph.scc(), [[1, 2], [3, 4]])

    def test_empty_graph_scc_errors(self):
        with self.assertRaises(EmptyGraphError):
            Graph().scc()

    def test_scc_is_deterministic(self):
        graph = build([(1, 2), (2, 1), (2, 3), (3, 2), (4, 5)])
        self.assertEqual(graph.scc(), graph.scc())

    def test_each_node_in_exactly_one_scc(self):
        graph = build([(1, 2), (2, 3), (3, 1), (3, 4), (4, 5), (5, 4)])
        seen = []
        for comp in graph.scc():
            seen.extend(comp)
        self.assertEqual(sorted(seen), [1, 2, 3, 4, 5])


class TestErrors(unittest.TestCase):
    def test_error_base_class(self):
        self.assertTrue(issubclass(GraphxError, Exception))
        self.assertTrue(issubclass(UnknownNodeError, GraphxError))
        self.assertTrue(issubclass(EmptyGraphError, GraphxError))

    def test_none_node_rejected(self):
        with self.assertRaises(UnknownNodeError):
            Graph().add_node(None)

    def test_unhashable_node_rejected(self):
        with self.assertRaises(UnknownNodeError):
            Graph().add_node([1, 2])

    def test_unknown_neighbor_rejected(self):
        graph = build([(1, 2)])
        with self.assertRaises(UnknownNodeError):
            graph.neighbors(9)

    def test_unknown_out_degree_rejected(self):
        graph = build([(1, 2)])
        with self.assertRaises(UnknownNodeError):
            graph.out_degree(9)

    def test_unknown_reachable_rejected(self):
        graph = build([(1, 2)])
        with self.assertRaises(UnknownNodeError):
            graph.reachable(1, 9)


if __name__ == "__main__":
    unittest.main()
