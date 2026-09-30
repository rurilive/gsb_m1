"""DirectedGraph 现有支配关系行为的锁定测试（基线，一字不改且必须全绿）。

锁的是逐点删点判可达这套现算口径在若干固定图上的结果：可达集合、删一点
之后的可达集合、全部支配点、直接支配点、支配树边、单次支配判断，以及非
法参数必须 fail fast、异常统一挂在基类下。
"""

import unittest

from domtree.dominator import (
    DirectedGraph,
    Erro,
    IllegalArgument,
    UnknownNode,
)


def build(nodes, edges):
    return DirectedGraph(nodes=nodes, edges=edges)


def ref_graph():
    """参照图：起点 s 经三条并行边汇到 d，再串到 e、f。"""
    return build(
        ["s", "a", "b", "c", "d", "e", "f"],
        [("s", "a"), ("s", "b"), ("s", "c"),
         ("a", "d"), ("b", "d"), ("c", "d"),
         ("d", "e"), ("e", "f")],
    )


class TestBuild(unittest.TestCase):
    def test_nodes_in_insertion_order(self):
        g = build(["a", "b", "c"], [("a", "b")])
        self.assertEqual(g.nodes(), ["a", "b", "c"])

    def test_add_node_is_idempotent(self):
        g = build(["a"], [])
        g.add_node("a")
        self.assertEqual(g.nodes(), ["a"])

    def test_add_edge_registers_endpoints(self):
        g = build([], [("u", "v")])
        self.assertTrue(g.has_node("u"))
        self.assertTrue(g.has_node("v"))
        self.assertEqual(g.edges(), [("u", "v")])

    def test_edges_sorted(self):
        g = build([], [("b", "c"), ("a", "b"), ("a", "c")])
        self.assertEqual(g.edges(), [("a", "b"), ("a", "c"), ("b", "c")])

    def test_has_edge_directed(self):
        g = build([], [("a", "b")])
        self.assertTrue(g.has_edge("a", "b"))
        self.assertFalse(g.has_edge("b", "a"))

    def test_neighbors_sorted(self):
        g = build([], [("a", "c"), ("a", "b")])
        self.assertEqual(g.neighbors("a"), ["b", "c"])

    def test_neighbors_of_unknown_raises(self):
        g = build(["a"], [])
        with self.assertRaises(UnknownNode):
            g.neighbors("ghost")

    def test_none_node_rejected(self):
        g = build(["a"], [])
        with self.assertRaises(IllegalArgument):
            g.add_node(None)
        with self.assertRaises(Erro):
            g.add_edge("a", None)


class TestReachable(unittest.TestCase):
    def test_reachable_includes_source(self):
        g = ref_graph()
        self.assertEqual(g.reachable_from("s"),
                         {"s", "a", "b", "c", "d", "e", "f"})

    def test_reachable_from_inner_node(self):
        g = ref_graph()
        self.assertEqual(g.reachable_from("a"), {"a", "d", "e", "f"})

    def test_reachable_from_leaf(self):
        g = ref_graph()
        self.assertEqual(g.reachable_from("f"), {"f"})

    def test_direction_respected(self):
        g = build([], [("a", "b")])
        self.assertEqual(g.reachable_from("b"), {"b"})

    def test_reachable_without_cuts_subtree(self):
        g = ref_graph()
        self.assertEqual(g.reachable_without("s", "d"), {"s", "a", "b", "c"})

    def test_reachable_without_source_is_empty(self):
        g = ref_graph()
        self.assertEqual(g.reachable_without("s", "s"), set())

    def test_unknown_source_raises(self):
        g = ref_graph()
        with self.assertRaises(UnknownNode):
            g.reachable_from("ghost")


class TestDominators(unittest.TestCase):
    def test_ref_graph_full_dominators(self):
        g = ref_graph()
        self.assertEqual(
            g.dominators("s"),
            {
                "s": ["s"],
                "a": ["a", "s"],
                "b": ["b", "s"],
                "c": ["c", "s"],
                "d": ["d", "s"],
                "e": ["d", "e", "s"],
                "f": ["d", "e", "f", "s"],
            },
        )

    def test_chain_dominators_nest(self):
        g = build(["n0", "n1", "n2", "n3"],
                  [("n0", "n1"), ("n1", "n2"), ("n2", "n3")])
        self.assertEqual(g.dominators("n0")["n2"], ["n0", "n1", "n2"])
        self.assertEqual(g.dominators("n0")["n3"], ["n0", "n1", "n2", "n3"])

    def test_diamond_middle_nodes_not_dominators(self):
        g = build(["r", "x", "y", "z"],
                  [("r", "x"), ("r", "y"), ("x", "z"), ("y", "z")])
        self.assertEqual(g.dominators("r")["z"], ["r", "z"])
        self.assertEqual(g.dominators("r")["x"], ["r", "x"])

    def test_unreachable_points_absent(self):
        g = build(["s", "t", "m", "k"],
                  [("s", "m"), ("t", "m"), ("m", "k")])
        dom = g.dominators("s")
        self.assertNotIn("t", dom)
        self.assertEqual(sorted(dom), ["k", "m", "s"])

    def test_candidate_start_excluded(self):
        g = ref_graph()
        self.assertEqual(g.dominators("s")["s"], ["s"])

    def test_unknown_start_raises(self):
        g = ref_graph()
        with self.assertRaises(UnknownNode):
            g.dominators("ghost")

    def test_deterministic(self):
        g = ref_graph()
        self.assertEqual(g.dominators("s"), g.dominators("s"))


class TestImmediateDominators(unittest.TestCase):
    def test_ref_graph_idom(self):
        g = ref_graph()
        self.assertEqual(
            g.immediate_dominators("s"),
            {"s": None, "a": "s", "b": "s", "c": "s",
             "d": "s", "e": "d", "f": "e"},
        )

    def test_single_node_start_is_none(self):
        g = build(["only"], [])
        self.assertEqual(g.immediate_dominators("only"), {"only": None})

    def test_cycle_idom(self):
        g = build(["p", "q"], [("p", "q"), ("q", "p")])
        self.assertEqual(g.immediate_dominators("p"), {"p": None, "q": "p"})

    def test_self_loop_idom(self):
        g = build(["a"], [("a", "a")])
        self.assertEqual(g.immediate_dominators("a"), {"a": None})

    def test_deterministic(self):
        g = ref_graph()
        self.assertEqual(g.immediate_dominators("s"),
                         g.immediate_dominators("s"))


class TestDominatorEdges(unittest.TestCase):
    def test_ref_graph_edges(self):
        g = ref_graph()
        self.assertEqual(
            g.dominator_edges("s"),
            [("d", "e"), ("e", "f"), ("s", "a"),
             ("s", "b"), ("s", "c"), ("s", "d")],
        )

    def test_single_node_has_no_edges(self):
        g = build(["only"], [])
        self.assertEqual(g.dominator_edges("only"), [])

    def test_edges_match_idom(self):
        g = ref_graph()
        idom = g.immediate_dominators("s")
        rebuilt = {(idom[v], v) for v in idom if idom[v] is not None}
        self.assertEqual(set(g.dominator_edges("s")), rebuilt)


class TestChildrenOf(unittest.TestCase):
    def test_root_children(self):
        g = ref_graph()
        self.assertEqual(g.children_of("s", "s"), ["a", "b", "c", "d"])

    def test_middle_children(self):
        g = ref_graph()
        self.assertEqual(g.children_of("s", "d"), ["e"])
        self.assertEqual(g.children_of("s", "e"), ["f"])

    def test_leaf_has_no_children(self):
        g = ref_graph()
        self.assertEqual(g.children_of("s", "f"), [])


class TestDominates(unittest.TestCase):
    def test_ref_graph_paths(self):
        g = ref_graph()
        self.assertTrue(g.dominates("s", "d", "f"))
        self.assertFalse(g.dominates("s", "a", "f"))
        self.assertFalse(g.dominates("s", "e", "d"))

    def test_self_and_start(self):
        g = ref_graph()
        self.assertTrue(g.dominates("s", "f", "f"))
        self.assertTrue(g.dominates("s", "s", "f"))

    def test_unreachable_target_is_false(self):
        g = build(["s", "t"], [])
        self.assertFalse(g.dominates("s", "s", "t"))

    def test_chain(self):
        g = build(["n0", "n1", "n2"], [("n0", "n1"), ("n1", "n2")])
        self.assertTrue(g.dominates("n0", "n1", "n2"))
        self.assertFalse(g.dominates("n0", "n2", "n1"))

    def test_unknown_node_raises(self):
        g = ref_graph()
        with self.assertRaises(UnknownNode):
            g.dominates("s", "ghost", "f")


class TestExceptionHierarchy(unittest.TestCase):
    def test_all_inherit_base(self):
        for exc in (IllegalArgument, UnknownNode):
            self.assertTrue(issubclass(exc, Erro))
        self.assertTrue(issubclass(Erro, Exception))


if __name__ == "__main__":
    unittest.main()
