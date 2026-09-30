"""pushrelabel 现有行为的锁定测试。

只覆盖当前朴素实现已经具备的能力：广度搜索逐条增广的最大流、按残量可达性
读出的最小割、平行边与零容量等边界、以及异常体系。预流推进、最高标号选择、
活跃点计数、两条路径的逐项比对与更完整的边界覆盖都留待新测试文件，本文件
一字不改。
"""

import unittest

from pushrelabel import (
    Edge,
    Erro,
    FlowNetwork,
    InvalidCapacityError,
    NoPathError,
    NodeNotFoundError,
    SelfLoopError,
    SourceSinkError,
    max_flow,
    min_cut,
)


def build_diamond():
    """菱形网络：s 分两路，两路再汇到 t，最大流为 5。"""
    net = FlowNetwork()
    net.add_edge("s", "a", 3)
    net.add_edge("s", "b", 2)
    net.add_edge("a", "b", 1)
    net.add_edge("a", "t", 2)
    net.add_edge("b", "t", 3)
    return net


def build_layered():
    """两级网络：s 到中层两条，中层到 t 两条，最大流为 5。"""
    net = FlowNetwork()
    net.add_edge("s", "a", 4)
    net.add_edge("s", "b", 3)
    net.add_edge("a", "c", 2)
    net.add_edge("a", "d", 2)
    net.add_edge("b", "c", 1)
    net.add_edge("c", "t", 3)
    net.add_edge("d", "t", 2)
    return net


class TestStructure(unittest.TestCase):
    def test_nodes_tracked_in_order(self):
        net = build_diamond()
        self.assertEqual(net.nodes(), ["s", "a", "b", "t"])

    def test_edges_in_insertion_order(self):
        net = build_diamond()
        self.assertEqual(
            [(e.src, e.dst, e.capacity) for e in net.edges()],
            [("s", "a", 3), ("s", "b", 2), ("a", "b", 1),
             ("a", "t", 2), ("b", "t", 3)],
        )

    def test_node_and_edge_counts(self):
        net = build_diamond()
        self.assertEqual(net.node_count(), 4)
        self.assertEqual(net.edge_count(), 5)

    def test_neighbors_are_unique(self):
        net = FlowNetwork()
        net.add_edge("s", "a", 1)
        net.add_edge("s", "a", 1)
        self.assertEqual(net.neighbors("s"), ["a"])

    def test_neighbors_of_unknown_node(self):
        with self.assertRaises(NodeNotFoundError):
            build_diamond().neighbors("ghost")

    def test_parallel_edges_kept_separately(self):
        net = FlowNetwork()
        net.add_edge("s", "t", 2)
        net.add_edge("s", "t", 3)
        self.assertEqual(net.edge_count(), 2)

    def test_has_node(self):
        net = build_diamond()
        self.assertTrue(net.has_node("a"))
        self.assertFalse(net.has_node("zzz"))


class TestCapacityValidation(unittest.TestCase):
    def test_negative_capacity_rejected(self):
        with self.assertRaises(InvalidCapacityError):
            FlowNetwork().add_edge("s", "t", -1)

    def test_bool_capacity_rejected(self):
        with self.assertRaises(InvalidCapacityError):
            FlowNetwork().add_edge("s", "t", True)

    def test_float_capacity_rejected(self):
        with self.assertRaises(InvalidCapacityError):
            FlowNetwork().add_edge("s", "t", 2.5)

    def test_zero_capacity_allowed(self):
        net = FlowNetwork()
        edge = net.add_edge("s", "t", 0)
        self.assertEqual(edge.capacity, 0)

    def test_self_loop_rejected(self):
        with self.assertRaises(SelfLoopError):
            FlowNetwork().add_edge("s", "s", 1)

    def test_rejected_edge_not_recorded(self):
        net = FlowNetwork()
        try:
            net.add_edge("s", "t", -3)
        except InvalidCapacityError:
            pass
        self.assertEqual(net.edge_count(), 0)


class TestMaxFlow(unittest.TestCase):
    def test_diamond_value(self):
        self.assertEqual(max_flow(build_diamond(), "s", "t").value, 5)

    def test_layered_value(self):
        self.assertEqual(max_flow(build_layered(), "s", "t").value, 5)

    def test_single_edge(self):
        net = FlowNetwork()
        net.add_edge("s", "t", 7)
        result = max_flow(net, "s", "t")
        self.assertEqual(result.value, 7)

    def test_parallel_edges_add_up(self):
        net = FlowNetwork()
        net.add_edge("s", "t", 2)
        net.add_edge("s", "t", 3)
        self.assertEqual(max_flow(net, "s", "t").value, 5)

    def test_no_path_yields_zero(self):
        net = FlowNetwork()
        net.add_edge("s", "x", 4)
        net.add_edge("y", "t", 4)
        self.assertEqual(max_flow(net, "s", "t").value, 0)

    def test_all_zero_capacity_yields_zero(self):
        net = FlowNetwork()
        net.add_edge("s", "a", 0)
        net.add_edge("a", "t", 0)
        self.assertEqual(max_flow(net, "s", "t").value, 0)

    def test_flow_never_exceeds_capacity(self):
        for net in (build_diamond(), build_layered()):
            result = max_flow(net, "s", "t")
            for edge in result.edges:
                self.assertGreaterEqual(edge.flow, 0)
                self.assertLessEqual(edge.flow, edge.capacity)

    def test_flow_conservation_at_internal_nodes(self):
        result = max_flow(build_layered(), "s", "t")
        for node in ("a", "b", "c", "d"):
            inflow = sum(e.flow for e in result.edges if e.dst == node)
            outflow = sum(e.flow for e in result.edges if e.src == node)
            self.assertEqual(inflow, outflow)

    def test_source_outflow_equals_value(self):
        result = max_flow(build_diamond(), "s", "t")
        outflow = sum(e.flow for e in result.edges if e.src == "s")
        self.assertEqual(outflow, result.value)

    def test_augmentations_counts_rounds(self):
        result = max_flow(build_diamond(), "s", "t")
        self.assertIsInstance(result.augmentations, int)
        self.assertGreater(result.augmentations, 0)

    def test_result_edges_are_copies(self):
        net = build_diamond()
        result = max_flow(net, "s", "t")
        result.edges[0].flow = 999
        self.assertEqual([e.flow for e in net.edges()], [0, 0, 0, 0, 0])

    def test_unknown_source(self):
        with self.assertRaises(NodeNotFoundError):
            max_flow(build_diamond(), "ghost", "t")

    def test_unknown_sink(self):
        with self.assertRaises(NodeNotFoundError):
            max_flow(build_diamond(), "s", "ghost")

    def test_source_equals_sink(self):
        with self.assertRaises(SourceSinkError):
            max_flow(build_diamond(), "s", "s")


class TestMinCut(unittest.TestCase):
    def test_value_matches_max_flow(self):
        net = build_layered()
        self.assertEqual(
            min_cut(net, "s", "t").value,
            max_flow(net, "s", "t").value,
        )

    def test_partition_covers_every_node_once(self):
        cut = min_cut(build_layered(), "s", "t")
        both = sorted(cut.source_side + cut.sink_side)
        self.assertEqual(both, sorted(build_layered().nodes()))

    def test_source_side_contains_source(self):
        cut = min_cut(build_diamond(), "s", "t")
        self.assertIn("s", cut.source_side)

    def test_sink_side_contains_sink(self):
        cut = min_cut(build_diamond(), "s", "t")
        self.assertIn("t", cut.sink_side)

    def test_cut_edges_cross_the_partition(self):
        cut = min_cut(build_layered(), "s", "t")
        for edge in cut.cut_edges:
            self.assertIn(edge.src, cut.source_side)
            self.assertIn(edge.dst, cut.sink_side)

    def test_cut_edges_capacity_sums_to_value(self):
        cut = min_cut(build_layered(), "s", "t")
        self.assertEqual(sum(e.capacity for e in cut.cut_edges), cut.value)

    def test_no_path_cut_is_chosen(self):
        net = FlowNetwork()
        net.add_edge("s", "x", 4)
        net.add_edge("y", "t", 4)
        cut = min_cut(net, "s", "t")
        self.assertEqual(cut.value, 0)


class TestDeterminism(unittest.TestCase):
    def test_repeat_runs_agree(self):
        first = max_flow(build_layered(), "s", "t")
        second = max_flow(build_layered(), "s", "t")
        self.assertEqual(first.value, second.value)
        self.assertEqual(
            [(e.src, e.dst, e.flow) for e in first.edges],
            [(e.src, e.dst, e.flow) for e in second.edges],
        )

    def test_network_untouched_by_query(self):
        net = build_diamond()
        before = [(e.src, e.dst, e.flow) for e in net.edges()]
        max_flow(net, "s", "t")
        min_cut(net, "s", "t")
        after = [(e.src, e.dst, e.flow) for e in net.edges()]
        self.assertEqual(before, after)

    def test_copy_is_isolated(self):
        net = build_diamond()
        clone = net.copy()
        for edge in clone.edges():
            edge.flow = 1
        self.assertEqual([e.flow for e in net.edges()], [0, 0, 0, 0, 0])

    def test_reachable_from_includes_source(self):
        self.assertIn("s", build_diamond().reachable_from("s"))


class TestErrors(unittest.TestCase):
    def test_all_errors_share_base(self):
        for exc in (
            InvalidCapacityError,
            NodeNotFoundError,
            SelfLoopError,
            SourceSinkError,
            NoPathError,
        ):
            self.assertTrue(issubclass(exc, Erro))

    def test_edge_residual_tracks_flow(self):
        edge = Edge("s", "t", 5, flow=2)
        self.assertEqual(edge.residual, 3)


if __name__ == "__main__":
    unittest.main()
