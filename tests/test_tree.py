"""lcatree 现有行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from lcatree.tree import Tree, TreeError, NodeNotFoundError, InvalidTreeError


def build_tree():
    # 根 10，10 的孩子 20、30，20 的孩子 40、50，30 的孩子 60。
    return Tree({10: None, 20: 10, 30: 10, 40: 20, 50: 20, 60: 30})


class TestBasics(unittest.TestCase):
    def test_root(self):
        self.assertEqual(build_tree().root, 10)

    def test_nodes_sorted(self):
        self.assertEqual(build_tree().nodes(), [10, 20, 30, 40, 50, 60])

    def test_depth(self):
        t = build_tree()
        self.assertEqual(t.depth(10), 0)
        self.assertEqual(t.depth(20), 1)
        self.assertEqual(t.depth(40), 2)

    def test_path_to_root(self):
        self.assertEqual(build_tree().path_to_root(40), [40, 20, 10])


class TestAncestorAndLca(unittest.TestCase):
    def test_is_ancestor_true(self):
        t = build_tree()
        self.assertTrue(t.is_ancestor(10, 60))
        self.assertTrue(t.is_ancestor(20, 40))

    def test_is_ancestor_self(self):
        self.assertTrue(build_tree().is_ancestor(30, 30))

    def test_is_ancestor_false(self):
        t = build_tree()
        self.assertFalse(t.is_ancestor(40, 20))
        self.assertFalse(t.is_ancestor(30, 40))

    def test_lca_siblings(self):
        self.assertEqual(build_tree().lca(40, 50), 20)

    def test_lca_cross_branch(self):
        self.assertEqual(build_tree().lca(40, 60), 10)

    def test_lca_self(self):
        t = build_tree()
        self.assertEqual(t.lca(40, 40), 40)
        self.assertEqual(t.lca(10, 60), 10)

    def test_distance(self):
        t = build_tree()
        self.assertEqual(t.distance(40, 50), 2)
        self.assertEqual(t.distance(40, 60), 4)
        self.assertEqual(t.distance(40, 40), 0)
        self.assertEqual(t.distance(10, 10), 0)


class TestPaths(unittest.TestCase):
    def test_path_downward(self):
        self.assertEqual(build_tree().path(10, 40), [10, 20, 40])

    def test_path_across_branches(self):
        self.assertEqual(build_tree().path(40, 60), [40, 20, 10, 30, 60])

    def test_path_same_node(self):
        self.assertEqual(build_tree().path(50, 50), [50])

    def test_path_sorted(self):
        self.assertEqual(build_tree().path_sorted(40, 60), [10, 20, 30, 40, 60])

    def test_on_path(self):
        t = build_tree()
        self.assertTrue(t.on_path(20, 40, 60))
        self.assertTrue(t.on_path(10, 40, 60))
        self.assertFalse(t.on_path(50, 40, 60))

    def test_paths_intersect(self):
        t = build_tree()
        self.assertTrue(t.paths_intersect(40, 50, 20, 60))
        self.assertFalse(t.paths_intersect(40, 50, 30, 60))


class TestEdges(unittest.TestCase):
    def test_single_node_tree(self):
        t = Tree({1: None})
        self.assertEqual(t.root, 1)
        self.assertEqual(t.lca(1, 1), 1)
        self.assertEqual(t.distance(1, 1), 0)
        self.assertEqual(t.path(1, 1), [1])

    def test_chain_tree(self):
        t = Tree({1: None, 2: 1, 3: 2, 4: 3, 5: 4})
        self.assertEqual(t.lca(5, 2), 2)
        self.assertEqual(t.distance(1, 5), 4)
        self.assertEqual(t.depth(5), 4)
        self.assertEqual(t.path(5, 1), [5, 4, 3, 2, 1])

    def test_missing_node(self):
        t = build_tree()
        with self.assertRaises(NodeNotFoundError):
            t.lca(40, 99)

    def test_errors_share_base(self):
        self.assertTrue(issubclass(NodeNotFoundError, TreeError))
        self.assertTrue(issubclass(InvalidTreeError, TreeError))

    def test_non_dict_rejected(self):
        with self.assertRaises(InvalidTreeError):
            Tree([(1, None)])

    def test_empty_rejected(self):
        with self.assertRaises(InvalidTreeError):
            Tree({})

    def test_two_roots_rejected(self):
        with self.assertRaises(InvalidTreeError):
            Tree({1: None, 2: None})

    def test_missing_parent_rejected(self):
        with self.assertRaises(InvalidTreeError):
            Tree({1: None, 2: 9})

    def test_cycle_rejected(self):
        with self.assertRaises(InvalidTreeError):
            Tree({1: 2, 2: 1})


if __name__ == "__main__":
    unittest.main()
