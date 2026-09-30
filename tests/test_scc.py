"""sccond 现有朴素行为的锁定测试（基线，一字不改）。"""

import unittest

from sccond import Digraph, GraphError, UnknownVertexError, naive_pair_count


def graph(vertices, edges):
    """按顶点列表与边列表造图。"""
    g = Digraph(vertices)
    for u, w in edges:
        g.add_edge(u, w)
    return g


def cycle_pair():
    """两个三元环，加上一条 2 到 3 的单向边，缩点后是一条两节点的链。"""
    edges = [(0, 1), (1, 2), (2, 0), (3, 4), (4, 3), (2, 3)]
    return graph([0, 1, 2, 3, 4], edges)


class TestConstruction(unittest.TestCase):
    def test_vertices_sorted(self):
        g = graph([3, 1, 2], [])
        self.assertEqual(g.vertices(), [1, 2, 3])

    def test_add_edge_autoadds(self):
        g = Digraph()
        g.add_edge(1, 2)
        self.assertEqual(g.vertices(), [1, 2])

    def test_self_loop_kept_once(self):
        g = graph([0], [(0, 0), (0, 0)])
        self.assertEqual(g.neighbors(0), [0])
        self.assertEqual(g.edge_count(), 1)

    def test_duplicate_edge_deduped(self):
        g = graph([0, 1], [(0, 1), (0, 1)])
        self.assertEqual(g.edge_count(), 1)

    def test_unknown_vertex_rejected(self):
        g = graph([0, 1], [(0, 1)])
        with self.assertRaises(UnknownVertexError):
            g.neighbors(9)

    def test_unknown_vertex_is_graph_error(self):
        self.assertTrue(issubclass(UnknownVertexError, GraphError))

    def test_out_degree(self):
        g = graph([0, 1, 2], [(0, 1), (0, 2)])
        self.assertEqual(g.out_degree(0), 2)


class TestNaiveReach(unittest.TestCase):
    def test_reachable_self(self):
        g = graph([0], [])
        self.assertTrue(g.reachable(0, 0))

    def test_reachable_chain(self):
        g = graph([0, 1, 2], [(0, 1), (1, 2)])
        self.assertTrue(g.reachable(0, 2))
        self.assertFalse(g.reachable(2, 0))

    def test_mutually_reachable_same_vertex(self):
        g = graph([5], [])
        self.assertTrue(g.mutually_reachable(5, 5))

    def test_mutually_reachable_two_cycle(self):
        g = graph([0, 1], [(0, 1), (1, 0)])
        self.assertTrue(g.mutually_reachable(0, 1))

    def test_reachable_set_sorted_with_self(self):
        g = graph([0, 1, 2], [(0, 1), (1, 2)])
        self.assertEqual(g.reachable_set(0), (0, 1, 2))

    def test_counters_count_searches(self):
        g = graph([0, 1, 2], [(0, 1), (1, 2)])
        g.reset_counters()
        g.reachable(0, 2)
        self.assertEqual(g.counters()["search_runs"], 1)
        self.assertGreater(g.counters()["visit_count"], 0)


class TestNaiveComponents(unittest.TestCase):
    def test_empty_graph(self):
        g = graph([], [])
        self.assertEqual(g.components(), [])
        self.assertEqual(g.component_count(), 0)
        self.assertFalse(g.is_strongly_connected())

    def test_single_vertex(self):
        g = graph([0], [])
        self.assertEqual(g.components(), [(0,)])
        self.assertTrue(g.is_strongly_connected())

    def test_no_edges_multiple_vertices(self):
        g = graph([0, 1, 2], [])
        self.assertEqual(g.components(), [(0,), (1,), (2,)])

    def test_self_loop_single_component(self):
        g = graph([0], [(0, 0)])
        self.assertEqual(g.components(), [(0,)])

    def test_two_cycle_one_component(self):
        g = graph([0, 1], [(0, 1), (1, 0)])
        self.assertEqual(g.components(), [(0, 1)])

    def test_chain_all_singletons(self):
        g = graph([0, 1, 2], [(0, 1), (1, 2)])
        self.assertEqual(g.components(), [(0,), (1,), (2,)])

    def test_two_cycles_ordered_by_min_vertex(self):
        g = cycle_pair()
        self.assertEqual(g.components(), [(0, 1, 2), (3, 4)])

    def test_component_of(self):
        g = cycle_pair()
        self.assertEqual(g.component_of(4), (3, 4))

    def test_whole_graph_strongly_connected(self):
        g = graph([0, 1, 2], [(0, 1), (1, 2), (2, 0)])
        self.assertTrue(g.is_strongly_connected())
        self.assertEqual(g.component_count(), 1)

    def test_naive_pair_count(self):
        self.assertEqual(naive_pair_count(4), 12)


class TestNaiveCondensation(unittest.TestCase):
    def test_condensation_is_dag(self):
        cg = cycle_pair().condensation()
        self.assertEqual(cg.vertices(), [0, 1])
        self.assertEqual(cg.edge_count(), 1)

    def test_condensation_single_component_has_no_edge(self):
        cg = graph([0, 1], [(0, 1), (1, 0)]).condensation()
        self.assertEqual(cg.vertices(), [0])
        self.assertEqual(cg.edge_count(), 0)

    def test_topological_order_chain(self):
        self.assertEqual(cycle_pair().topological_order(), [0, 1])

    def test_topological_order_dag_itself(self):
        g = graph([0, 1, 2], [(0, 1), (0, 2), (1, 2)])
        self.assertEqual(g.topological_order(), [0, 1, 2])

    def test_longest_chain_length(self):
        length, path = cycle_pair().longest_chain()
        self.assertEqual(length, 1)
        self.assertEqual(path, [0, 1])

    def test_longest_chain_dag(self):
        g = graph([0, 1, 2, 3], [(0, 1), (1, 2), (2, 3), (0, 3)])
        length, path = g.longest_chain()
        self.assertEqual(length, 3)
        self.assertEqual(path, [0, 1, 2, 3])

    def test_longest_chain_single_vertex(self):
        self.assertEqual(graph([0], []).longest_chain(), (0, [0]))

    def test_longest_chain_empty(self):
        self.assertEqual(graph([], []).longest_chain(), (0, []))

    def test_source_and_sink(self):
        g = cycle_pair()
        self.assertEqual(g.source_components(), [0])
        self.assertEqual(g.sink_components(), [1])

    def test_source_sink_single_node(self):
        g = graph([0], [])
        self.assertEqual(g.source_components(), [0])
        self.assertEqual(g.sink_components(), [0])


class TestNaiveComponentReach(unittest.TestCase):
    def test_reachable_components(self):
        g = cycle_pair()
        self.assertEqual(g.reachable_components(1), (0, 1))

    def test_reachable_components_from_sink(self):
        g = cycle_pair()
        self.assertEqual(g.reachable_components(4), (1,))

    def test_transitive_closure(self):
        g = graph([0, 1, 2], [(0, 1), (1, 2)])
        closure = g.transitive_closure()
        self.assertEqual(closure[0], (0, 1, 2))
        self.assertEqual(closure[2], (2,))

    def test_max_reachable_component_size(self):
        g = cycle_pair()
        self.assertEqual(g.max_reachable_component_size(0), 3)

    def test_max_reachable_component_size_single(self):
        g = graph([0], [])
        self.assertEqual(g.max_reachable_component_size(0), 1)


if __name__ == "__main__":
    unittest.main()
