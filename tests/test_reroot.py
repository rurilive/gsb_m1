"""基线测试：锁住改造前 Reroot 的现状行为。

这些用例描述的是当前"每个结点单独当根重走整棵树"实现对外可见的事实，
改造后必须继续成立，因此本文件一字不得修改。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reroot.core import (
    DisconnectedError,
    Reroot,
    RerootError,
    RerootInputError,
    UnknownNodeError,
)


def build(n, edges):
    tree = Reroot()
    tree.load(n, edges)
    return tree


class TestLoadAndValidation(unittest.TestCase):
    def test_single_node_tree(self):
        tree = build(1, [])
        self.assertEqual(tree.node_count(), 1)
        self.assertEqual(tree.subtree_sizes(0), {0: 1})
        self.assertEqual(tree.distance_sum(0), 0)
        self.assertEqual(tree.deepest_subtree(0), 0)

    def test_non_positive_n_rejected(self):
        with self.assertRaises(RerootInputError):
            build(0, [])

    def test_edge_endpoint_out_of_range_rejected(self):
        with self.assertRaises(RerootInputError):
            build(2, [(0, 5)])

    def test_malformed_edge_rejected(self):
        with self.assertRaises(RerootInputError):
            build(3, [(0, 1, 2), (1, 2)])

    def test_wrong_edge_count_rejected(self):
        with self.assertRaises(DisconnectedError):
            build(3, [(0, 1)])

    def test_disconnected_edges_rejected(self):
        # 三条边连成三角形，结点 3 被孤立，没有覆盖全部结点
        with self.assertRaises(DisconnectedError):
            build(4, [(0, 1), (1, 2), (0, 2)])

    def test_query_before_load_rejected(self):
        with self.assertRaises(RerootInputError):
            Reroot().node_count()


class TestSubtreeSizes(unittest.TestCase):
    def test_sizes_on_small_tree(self):
        # 0 为根，子结点 1、2；1 的子结点 3、4
        tree = build(5, [(0, 1), (0, 2), (1, 3), (1, 4)])
        self.assertEqual(tree.subtree_sizes(0), {0: 5, 1: 3, 2: 1, 3: 1, 4: 1})
        self.assertEqual(tree.subtree_sizes(1), {0: 2, 1: 5, 2: 1, 3: 1, 4: 1})
        self.assertEqual(tree.subtree_sizes(2), {0: 4, 1: 3, 2: 5, 3: 1, 4: 1})

    def test_chain_sizes_from_tail(self):
        tree = build(4, [(0, 1), (1, 2), (2, 3)])
        self.assertEqual(tree.subtree_sizes(0), {0: 4, 1: 3, 2: 2, 3: 1})
        self.assertEqual(tree.subtree_sizes(3), {0: 1, 1: 2, 2: 3, 3: 4})


class TestDistanceSums(unittest.TestCase):
    def test_small_tree(self):
        tree = build(5, [(0, 1), (0, 2), (1, 3), (1, 4)])
        self.assertEqual(tree.distance_sum(0), 6)
        self.assertEqual(tree.distance_sum(1), 5)
        self.assertEqual(
            tree.all_distance_sums(), {0: 6, 1: 5, 2: 9, 3: 8, 4: 8}
        )

    def test_chain(self):
        tree = build(4, [(0, 1), (1, 2), (2, 3)])
        self.assertEqual(
            tree.all_distance_sums(), {0: 6, 1: 4, 2: 4, 3: 6}
        )

    def test_star(self):
        tree = build(4, [(0, 1), (0, 2), (0, 3)])
        self.assertEqual(
            tree.all_distance_sums(), {0: 3, 1: 5, 2: 5, 3: 5}
        )

    def test_two_node_tree(self):
        tree = build(2, [(0, 1)])
        self.assertEqual(tree.all_distance_sums(), {0: 1, 1: 1})


class TestDeepestSubtree(unittest.TestCase):
    def test_small_tree(self):
        tree = build(5, [(0, 1), (0, 2), (1, 3), (1, 4)])
        self.assertEqual(
            tree.all_deepest_subtrees(), {0: 2, 1: 2, 2: 3, 3: 3, 4: 3}
        )

    def test_chain(self):
        tree = build(4, [(0, 1), (1, 2), (2, 3)])
        self.assertEqual(
            tree.all_deepest_subtrees(), {0: 3, 1: 2, 2: 2, 3: 3}
        )

    def test_star(self):
        tree = build(4, [(0, 1), (0, 2), (0, 3)])
        self.assertEqual(
            tree.all_deepest_subtrees(), {0: 1, 1: 2, 2: 2, 3: 2}
        )


class TestVisitCountAndErrors(unittest.TestCase):
    def test_visit_count_is_square(self):
        # 逐根深搜，每个根都走满整棵树，总次数为结点数的平方
        tree = build(5, [(0, 1), (0, 2), (1, 3), (1, 4)])
        self.assertEqual(tree.visit_count(), 25)
        self.assertEqual(build(1, []).visit_count(), 1)

    def test_unknown_node_raises(self):
        tree = build(3, [(0, 1), (0, 2)])
        with self.assertRaises(UnknownNodeError):
            tree.subtree_sizes(9)
        with self.assertRaises(UnknownNodeError):
            tree.distance_sum(-1)
        with self.assertRaises(UnknownNodeError):
            tree.deepest_subtree(3)

    def test_errors_share_base_class(self):
        self.assertTrue(issubclass(RerootInputError, RerootError))
        self.assertTrue(issubclass(UnknownNodeError, RerootError))
        self.assertTrue(issubclass(DisconnectedError, RerootError))


class TestDeterminism(unittest.TestCase):
    def test_fixed_input_repeatable(self):
        edges = [(0, 1), (0, 2), (1, 3), (1, 4), (2, 5), (2, 6)]

        def run():
            tree = build(7, edges)
            return (
                tree.all_distance_sums(),
                tree.all_deepest_subtrees(),
                tree.subtree_sizes(0),
                tree.visit_count(),
            )

        self.assertEqual(run(), run())


if __name__ == "__main__":
    unittest.main()
