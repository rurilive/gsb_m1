"""MinCostFlow 朴素实现的行为基线测试。

锁住现状：广度优先反复增广给出最大流，费用按增广路累加；
在费用结构上有意构造的图上只保证流量最大、费用并非最小。
"""

import unittest

from mcmf.flow import BadEdge, Erro, MinCostFlow


def run(ctx, edges, s, t):
    """按边表建图并跑一次朴素最大流，返回求解器。"""
    for u, v, cap, cost in edges:
        ctx.add_edge(u, v, cap, cost)
    ctx.max_flow(s, t)
    return ctx


class TestExceptions(unittest.TestCase):
    def test_error_hierarchy(self):
        self.assertTrue(issubclass(Erro, Exception))
        self.assertTrue(issubclass(BadEdge, Erro))

    def test_negative_capacity_raises(self):
        ctx = MinCostFlow()
        with self.assertRaises(BadEdge):
            ctx.add_edge("s", "t", -1, 0)

    def test_non_int_cost_raises(self):
        ctx = MinCostFlow()
        with self.assertRaises(BadEdge):
            ctx.add_edge("s", "t", 1, 1.5)

    def test_unknown_node_raises(self):
        ctx = MinCostFlow()
        ctx.add_edge("s", "a", 1, 0)
        with self.assertRaises(BadEdge):
            ctx.max_flow("s", "ghost")


class TestMaxFlow(unittest.TestCase):
    def test_chain(self):
        ctx = run(MinCostFlow(), [("s", "a", 3, 2), ("a", "t", 2, 1)], "s", "t")
        self.assertEqual(ctx.flow_value(), 2)
        self.assertEqual(ctx.flow_cost(), 6)

    def test_single_edge(self):
        ctx = run(MinCostFlow(), [("s", "t", 4, 7)], "s", "t")
        self.assertEqual(ctx.flow_value(), 4)
        self.assertEqual(ctx.flow_cost(), 28)

    def test_parallel_edges(self):
        ctx = run(MinCostFlow(), [("s", "t", 1, 5), ("s", "t", 2, 3)], "s", "t")
        self.assertEqual(ctx.flow_value(), 3)

    def test_no_path_returns_zero(self):
        edges = [("s", "x", 5, 0), ("y", "t", 5, 0)]
        ctx = run(MinCostFlow(), edges, "s", "t")
        self.assertEqual(ctx.flow_value(), 0)
        self.assertEqual(ctx.flow_cost(), 0)

    def test_zero_capacity_edge_is_dead(self):
        ctx = run(MinCostFlow(), [("s", "t", 0, 9)], "s", "t")
        self.assertEqual(ctx.flow_value(), 0)

    def test_source_equals_sink(self):
        ctx = run(MinCostFlow(), [("s", "t", 1, 0)], "s", "s")
        self.assertEqual(ctx.flow_value(), 0)

    def test_negative_cost_edge_still_maximizes(self):
        ctx = run(MinCostFlow(), [("s", "a", 1, -3), ("a", "t", 1, 0)], "s", "t")
        self.assertEqual(ctx.flow_value(), 1)
        self.assertEqual(ctx.flow_cost(), -3)

    def test_max_flow_is_idempotent(self):
        ctx = MinCostFlow()
        ctx.add_edge("s", "a", 2, 1)
        ctx.add_edge("a", "t", 2, 1)
        self.assertEqual(ctx.max_flow("s", "t"), 2)
        self.assertEqual(ctx.max_flow("s", "t"), 2)
        self.assertEqual(ctx.flow_cost(), 4)

    def test_repeated_runs_are_deterministic(self):
        edges = [("s", "a", 1, 4), ("s", "b", 1, 1), ("a", "t", 1, 1), ("b", "t", 1, 0)]

        def once():
            ctx = run(MinCostFlow(), list(edges), "s", "t")
            return ctx.flow_value(), ctx.flow_cost()

        self.assertEqual(once(), once())


class TestEdgeFlows(unittest.TestCase):
    def test_edge_flows_shape(self):
        ctx = run(MinCostFlow(), [("s", "t", 4, 7)], "s", "t")
        self.assertEqual(ctx.edge_flows(), [("s", "t", 4, 7, 4)])

    def test_nodes_in_insertion_order(self):
        ctx = MinCostFlow()
        ctx.add_edge("s", "a", 1, 0)
        ctx.add_edge("a", "t", 1, 0)
        self.assertEqual(ctx.nodes(), ["s", "a", "t"])


class TestNaiveIsNotOptimal(unittest.TestCase):
    """源点只放行一个单位，广搜先撞上三跳的贵通路，把更长的便宜通路挡在门外。"""

    EDGES = [
        ("s", "x", 1, 0),
        ("x", "a", 1, 0),
        ("a", "t", 1, 10),
        ("x", "b", 1, 0),
        ("b", "c", 1, 0),
        ("c", "t", 1, 0),
    ]

    def test_flow_is_maximal_but_cost_is_naive(self):
        ctx = run(MinCostFlow(), list(self.EDGES), "s", "t")
        self.assertEqual(ctx.flow_value(), 1)
        self.assertEqual(ctx.flow_cost(), 10)


if __name__ == "__main__":
    unittest.main()
