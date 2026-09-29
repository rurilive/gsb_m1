"""WalkTree 现状行为的锁定测试（基线，一字不改且必须全绿）。

锁的是一个固定小树上的逐节点遍历结果：深度、最近公共祖先、路径和、
子树和、路径加，以及非法输入必须 fail fast。
"""

import unittest

from treepath.tree import NodeNotFound, TreeError, WalkTree

# 固定树：
#        1
#       / \
#      2   3
#     / \   \
#    4   5   6
FIXED_EDGES = [(1, 2), (1, 3), (2, 4), (2, 5), (3, 6)]
FIXED_WEIGHTS = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6}


def build_tree():
    t = WalkTree(1, FIXED_EDGES)
    for node, value in FIXED_WEIGHTS.items():
        t.set_weight(node, value)
    return t


class TestWalkTreeStructure(unittest.TestCase):
    def test_root_and_nodes(self):
        t = build_tree()
        self.assertEqual(t.root, 1)
        self.assertEqual(sorted(t.nodes()), [1, 2, 3, 4, 5, 6])

    def test_children_preserve_order(self):
        t = build_tree()
        self.assertEqual(t.children(1), [2, 3])
        self.assertEqual(t.children(2), [4, 5])
        self.assertEqual(t.children(6), [])

    def test_children_returns_copy(self):
        t = build_tree()
        got = t.children(2)
        got.append(999)
        self.assertEqual(t.children(2), [4, 5])

    def test_edges_may_be_given_out_of_order(self):
        t = WalkTree(1, [(2, 5), (3, 6), (1, 3), (2, 4), (1, 2)])
        self.assertEqual(t.depth(6), 2)
        self.assertEqual(t.children(1), [2, 3])


class TestWalkTreeWeights(unittest.TestCase):
    def test_weight_reads_back(self):
        t = build_tree()
        self.assertEqual(t.weight(4), 4)

    def test_unset_weight_is_zero(self):
        t = WalkTree(1, [(1, 2)])
        self.assertEqual(t.weight(2), 0)


class TestWalkTreeNaiveQueries(unittest.TestCase):
    def test_depth(self):
        t = build_tree()
        self.assertEqual(t.depth(1), 0)
        self.assertEqual(t.depth(2), 1)
        self.assertEqual(t.depth(4), 2)
        self.assertEqual(t.depth(6), 2)

    def test_lca(self):
        t = build_tree()
        self.assertEqual(t.lca(4, 5), 2)
        self.assertEqual(t.lca(4, 6), 1)
        self.assertEqual(t.lca(5, 3), 1)

    def test_lca_when_node_is_its_own_ancestor(self):
        t = build_tree()
        self.assertEqual(t.lca(2, 4), 2)
        self.assertEqual(t.lca(1, 6), 1)
        self.assertEqual(t.lca(4, 4), 4)

    def test_path_nodes(self):
        t = build_tree()
        self.assertEqual(t.path_nodes(4, 5), [4, 2, 5])
        self.assertEqual(t.path_nodes(4, 6), [4, 2, 1, 3, 6])
        self.assertEqual(t.path_nodes(2, 4), [2, 4])

    def test_path_sum(self):
        t = build_tree()
        self.assertEqual(t.path_sum(4, 5), 11)
        self.assertEqual(t.path_sum(4, 6), 16)
        self.assertEqual(t.path_sum(3, 3), 3)

    def test_subtree_sum(self):
        t = build_tree()
        self.assertEqual(t.subtree_sum(2), 11)
        self.assertEqual(t.subtree_sum(3), 9)
        self.assertEqual(t.subtree_sum(1), 21)
        self.assertEqual(t.subtree_sum(4), 4)


class TestWalkTreeNaiveUpdate(unittest.TestCase):
    def test_update_returns_touched_nodes(self):
        t = build_tree()
        touched = t.update(4, 6, 1)
        self.assertEqual(touched, [4, 2, 1, 3, 6])

    def test_update_adds_each_node_once(self):
        t = build_tree()
        t.update(4, 6, 1)
        self.assertEqual(t.weight(4), 5)
        self.assertEqual(t.weight(2), 3)
        self.assertEqual(t.weight(1), 2)
        self.assertEqual(t.weight(3), 4)
        self.assertEqual(t.weight(6), 7)
        # 路径外节点不受影响
        self.assertEqual(t.weight(5), 5)

    def test_update_then_path_sum_matches(self):
        t = build_tree()
        t.update(4, 6, 2)
        self.assertEqual(t.path_sum(4, 6), 16 + 2 * 5)


class TestWalkTreeErrors(unittest.TestCase):
    def test_node_not_found_is_tree_error(self):
        self.assertTrue(issubclass(NodeNotFound, TreeError))

    def test_unknown_node_raises(self):
        t = build_tree()
        with self.assertRaises(NodeNotFound):
            t.depth(99)
        with self.assertRaises(NodeNotFound):
            t.path_sum(1, 99)
        with self.assertRaises(TreeError):
            t.children(99)

    def test_duplicate_child_rejected(self):
        with self.assertRaises(TreeError):
            WalkTree(1, [(1, 2), (2, 3), (1, 3)])

    def test_cycle_rejected(self):
        with self.assertRaises(TreeError):
            WalkTree(1, [(1, 2), (2, 3), (3, 1)])

    def test_unreachable_node_rejected(self):
        with self.assertRaises(TreeError):
            WalkTree(1, [(2, 3)])


if __name__ == "__main__":
    unittest.main()
