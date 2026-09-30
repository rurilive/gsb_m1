"""dagtopo 现有行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from dagtopo.graph import (
    DirectedGraph,
    TopoError,
    InvalidGraphError,
    NodeNotFoundError,
)


def diamond():
    # 菱形依赖：0、1 都指向 2，2 再指向 3。
    return DirectedGraph(4, [(0, 2), (1, 2), (2, 3)])


class TestBasics(unittest.TestCase):
    def test_counts(self):
        g = diamond()
        self.assertEqual(g.node_count(), 4)
        self.assertEqual(g.edge_count(), 3)

    def test_nodes_edges(self):
        g = diamond()
        self.assertEqual(g.nodes(), [0, 1, 2, 3])
        self.assertEqual(g.edges()[0], (0, 2))

    def test_in_degrees(self):
        self.assertEqual(diamond().in_degrees(), [0, 0, 2, 1])


class TestTopologicalOrder(unittest.TestCase):
    def test_diamond_order(self):
        self.assertEqual(diamond().topological_order(), [0, 1, 2, 3])

    def test_chain(self):
        g = DirectedGraph(4, [(0, 1), (1, 2), (2, 3)])
        self.assertEqual(g.topological_order(), [0, 1, 2, 3])

    def test_smallest_available(self):
        # 0、1 都无入度，先取编号小的 0，再取 1。
        g = DirectedGraph(3, [(0, 2), (1, 2)])
        self.assertEqual(g.topological_order(), [0, 1, 2])

    def test_cycle_returns_none(self):
        self.assertIsNone(DirectedGraph(2, [(0, 1), (1, 0)]).topological_order())

    def test_empty_graph(self):
        self.assertEqual(DirectedGraph(1, []).topological_order(), [0])

    def test_repeat_run_equal(self):
        g = diamond()
        self.assertEqual(g.topological_order(), g.topological_order())


class TestCycleNodes(unittest.TestCase):
    def test_no_cycle(self):
        self.assertEqual(diamond().cycle_nodes(), [])

    def test_two_cycle(self):
        self.assertEqual(DirectedGraph(2, [(0, 1), (1, 0)]).cycle_nodes(), [0, 1])

    def test_cycle_after_chain(self):
        # 0 到 1 到 2 再到 3，然后 3 回到 1，环是 1、2、3。
        g = DirectedGraph(4, [(0, 1), (1, 2), (2, 3), (3, 1)])
        self.assertEqual(g.cycle_nodes(), [1, 2, 3])

    def test_self_loop(self):
        self.assertEqual(DirectedGraph(1, [(0, 0)]).cycle_nodes(), [0])


class TestSchedule(unittest.TestCase):
    def test_earliest_start(self):
        # 0 工期 3，1 工期 2，2 要等两者都完成，最早开始是 3。
        g = DirectedGraph(3, [(0, 2), (1, 2)])
        self.assertEqual(g.earliest_start([3, 2, 1]), [0, 0, 3])

    def test_critical_path(self):
        g = DirectedGraph(3, [(0, 2), (1, 2)])
        # 点 1 工期 2，点 0 工期 3，故关键链是 0 到 2。
        self.assertEqual(g.critical_path([3, 2, 1]), [0, 2])

    def test_critical_path_len(self):
        self.assertEqual(len(diamond().critical_path([1, 1, 1, 1])), 3)

    def test_durations_as_dict(self):
        g = diamond()
        self.assertEqual(g.earliest_start({0: 1, 1: 1, 2: 1, 3: 1}), [0, 0, 1, 2])

    def test_earliest_start_cycle_none(self):
        self.assertIsNone(DirectedGraph(2, [(0, 1), (1, 0)]).earliest_start([1, 1]))

    def test_isolation_no_edges(self):
        g = DirectedGraph(3, [])
        self.assertEqual(g.earliest_start([2, 2, 2]), [0, 0, 0])
        self.assertEqual(g.critical_path([2, 2, 2]), [0])


class TestReachability(unittest.TestCase):
    def test_reachable_counts(self):
        # 0 能到 2、3，共两个。
        g = DirectedGraph(4, [(0, 2), (2, 3)])
        self.assertEqual(g.reachable_counts(), [2, 0, 1, 0])

    def test_reverse_reachable_counts(self):
        g = DirectedGraph(4, [(0, 2), (2, 3)])
        self.assertEqual(g.reverse_reachable_counts(), [0, 0, 1, 2])

    def test_cycle_reach(self):
        g = DirectedGraph(2, [(0, 1), (1, 0)])
        self.assertEqual(g.reachable_counts(), [1, 1])


class TestCounters(unittest.TestCase):
    def test_counters_after_order(self):
        g = diamond()
        g.reset_counters()
        g.topological_order()
        c = g.counters()
        self.assertGreater(c["scan_visits"], 0)
        self.assertGreater(c["edge_visits"], 0)

    def test_counters_reset(self):
        g = diamond()
        g.topological_order()
        g.reset_counters()
        self.assertEqual(g.counters(), {"scan_visits": 0, "edge_visits": 0})


class TestErrors(unittest.TestCase):
    def test_errors_share_base(self):
        self.assertTrue(issubclass(InvalidGraphError, TopoError))
        self.assertTrue(issubclass(NodeNotFoundError, TopoError))

    def test_zero_nodes_rejected(self):
        with self.assertRaises(InvalidGraphError):
            DirectedGraph(0, [])

    def test_non_list_edges_rejected(self):
        with self.assertRaises(InvalidGraphError):
            DirectedGraph(3, "abc")

    def test_bad_edge_shape_rejected(self):
        with self.assertRaises(InvalidGraphError):
            DirectedGraph(3, [(0, 1, 2)])

    def test_endpoint_out_of_range(self):
        with self.assertRaises(InvalidGraphError):
            DirectedGraph(3, [(0, 9)])

    def test_bad_duration(self):
        with self.assertRaises(InvalidGraphError):
            diamond().earliest_start([1, 1, -1, 1])

    def test_duration_length_mismatch(self):
        with self.assertRaises(InvalidGraphError):
            diamond().earliest_start([1, 1, 1])

    def test_unknown_node(self):
        with self.assertRaises(NodeNotFoundError):
            diamond()._require_node(99)


if __name__ == "__main__":
    unittest.main()
