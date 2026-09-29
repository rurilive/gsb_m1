"""FlatForest 现状行为的锁定测试（基线，一字不改且必须全绿）。

锁的是一片固定森林上的邻接集合与当场遍历结果：节点登记、邻居视图、
连边断边、连通性、路径和、子树和、路径加、连通分量计数，以及非法操作
必须 fail fast。
"""

import unittest

from lctlib.forest import FlatForest, LctError, NoSuchEdge, NoSuchNode

# 固定森林：一片是 1-2-3、2-4 的树，另一片是 5-6 的树。
FIXED_LINKS = [(1, 2), (2, 3), (2, 4), (5, 6)]
FIXED_WEIGHTS = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6}


def build_forest():
    f = FlatForest()
    for node in range(1, 7):
        f.add_node(node)
    for u, v in FIXED_LINKS:
        f.link(u, v)
    for node, value in FIXED_WEIGHTS.items():
        f.set_weight(node, value)
    return f


class TestFlatForestStructure(unittest.TestCase):
    def test_nodes_preserve_registration_order(self):
        f = build_forest()
        self.assertEqual(f.nodes(), [1, 2, 3, 4, 5, 6])

    def test_neighbors_read_back(self):
        f = build_forest()
        self.assertEqual(f.neighbors(2), {1, 3, 4})
        self.assertEqual(f.neighbors(1), {2})
        self.assertEqual(f.neighbors(6), {5})

    def test_neighbors_returns_copy(self):
        f = build_forest()
        got = f.neighbors(2)
        got.add(999)
        self.assertEqual(f.neighbors(2), {1, 3, 4})

    def test_has_edge_and_edge_count(self):
        f = build_forest()
        self.assertTrue(f.has_edge(2, 4))
        self.assertTrue(f.has_edge(4, 2))
        self.assertFalse(f.has_edge(1, 4))
        self.assertEqual(f.edge_count(), 4)

    def test_duplicate_add_node_rejected(self):
        f = build_forest()
        with self.assertRaises(LctError):
            f.add_node(1)


class TestFlatForestConnectivity(unittest.TestCase):
    def test_connected_within_one_tree(self):
        f = build_forest()
        self.assertTrue(f.connected(1, 3))
        self.assertTrue(f.connected(3, 4))

    def test_node_connects_to_itself(self):
        f = build_forest()
        self.assertTrue(f.connected(4, 4))

    def test_disconnected_pair(self):
        f = build_forest()
        self.assertFalse(f.connected(1, 5))
        self.assertFalse(f.connected(3, 6))

    def test_component_count(self):
        f = build_forest()
        self.assertEqual(f.component_count(), 2)

    def test_singleton_is_own_component(self):
        f = build_forest()
        f.add_node(7)
        self.assertEqual(f.component_count(), 3)
        self.assertFalse(f.connected(7, 1))


class TestFlatForestPathQueries(unittest.TestCase):
    def test_path_sum(self):
        f = build_forest()
        self.assertEqual(f.path_sum(3, 4), 9)
        self.assertEqual(f.path_sum(1, 3), 6)
        self.assertEqual(f.path_sum(3, 3), 3)

    def test_path_sum_across_a_single_edge(self):
        f = build_forest()
        self.assertEqual(f.path_sum(5, 6), 11)

    def test_subtree_sum(self):
        f = build_forest()
        self.assertEqual(f.subtree_sum(2, 1), 9)
        self.assertEqual(f.subtree_sum(3, 1), 3)
        self.assertEqual(f.subtree_sum(6, 5), 6)

    def test_subtree_sum_at_root_covers_its_whole_tree(self):
        f = build_forest()
        # 给定根 1 时以 1 为根的子树就是 1 所在的那棵树，另一棵树不算进来
        self.assertEqual(f.subtree_sum(1, 1), 10)

    def test_subtree_sum_on_disconnected_pair_fails(self):
        f = build_forest()
        with self.assertRaises(LctError):
            f.subtree_sum(1, 5)

    def test_path_sum_on_disconnected_pair_fails(self):
        f = build_forest()
        with self.assertRaises(LctError):
            f.path_sum(1, 5)


class TestFlatForestPathAdd(unittest.TestCase):
    def test_path_add_returns_touched_nodes(self):
        f = build_forest()
        touched = f.path_add(3, 4, 1)
        self.assertEqual(touched, [3, 2, 4])

    def test_path_add_updates_only_path_nodes(self):
        f = build_forest()
        f.path_add(3, 4, 1)
        self.assertEqual(f.weight(3), 4)
        self.assertEqual(f.weight(2), 3)
        self.assertEqual(f.weight(4), 5)
        # 路径外节点不受影响
        self.assertEqual(f.weight(1), 1)
        self.assertEqual(f.weight(5), 5)

    def test_path_add_then_sum_matches(self):
        f = build_forest()
        f.path_add(3, 4, 2)
        self.assertEqual(f.path_sum(3, 4), 9 + 2 * 3)

    def test_path_add_on_disconnected_pair_fails(self):
        f = build_forest()
        with self.assertRaises(LctError):
            f.path_add(1, 5, 1)


class TestFlatForestLinkCut(unittest.TestCase):
    def test_link_then_connected(self):
        f = FlatForest()
        for node in range(1, 5):
            f.add_node(node)
        f.link(1, 2)
        self.assertTrue(f.connected(1, 2))
        self.assertFalse(f.connected(1, 3))
        self.assertEqual(f.component_count(), 3)

    def test_cut_splits_the_tree(self):
        f = build_forest()
        f.cut(2, 4)
        self.assertFalse(f.has_edge(2, 4))
        self.assertFalse(f.connected(1, 4))
        self.assertTrue(f.connected(1, 3))
        self.assertEqual(f.component_count(), 3)
        with self.assertRaises(LctError):
            f.path_sum(2, 4)

    def test_cut_all_edges_leaves_a_bare_forest(self):
        f = build_forest()
        for u, v in FIXED_LINKS:
            f.cut(u, v)
        self.assertEqual(f.edge_count(), 0)
        self.assertEqual(f.component_count(), 6)

    def test_link_refuses_a_cycle(self):
        f = build_forest()
        with self.assertRaises(LctError):
            f.link(1, 4)

    def test_link_refuses_self_loop(self):
        f = build_forest()
        with self.assertRaises(LctError):
            f.link(2, 2)

    def test_link_refuses_duplicate_edge(self):
        f = build_forest()
        with self.assertRaises(LctError):
            f.link(2, 1)

    def test_cut_missing_edge_fails(self):
        f = build_forest()
        with self.assertRaises(NoSuchEdge):
            f.cut(1, 4)


class TestFlatForestErrors(unittest.TestCase):
    def test_error_hierarchy(self):
        self.assertTrue(issubclass(NoSuchNode, LctError))
        self.assertTrue(issubclass(NoSuchEdge, LctError))

    def test_unknown_node_raises(self):
        f = build_forest()
        with self.assertRaises(NoSuchNode):
            f.neighbors(99)
        with self.assertRaises(NoSuchNode):
            f.weight(99)
        with self.assertRaises(NoSuchNode):
            f.path_sum(1, 99)
        with self.assertRaises(NoSuchNode):
            f.link(1, 99)


if __name__ == "__main__":
    unittest.main()
