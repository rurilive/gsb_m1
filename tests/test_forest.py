"""朴素深搜森林的锁定测试。

只覆盖当前实现已经具备的能力：连通性、加边、删边、路径点权和、
路径点权最值、点权设置，以及未知点与参数错误的报错口径。新增能力
（伸展树辅助树路径、打通与换根、两条路径逐项对照、各项边界）另开
测试文件，本文件一字不改。
"""

import unittest

from lct import Erro, Forest
from lct.forest import ArgErro, CutErro, LinkErro, UnknownNodeErro


class TestBuildAndValues(unittest.TestCase):
    def test_size_and_initial_values(self):
        forest = Forest(5)
        self.assertEqual(forest.size(), 5)
        for node in range(5):
            self.assertEqual(forest.get_value(node), 0)

    def test_empty_forest(self):
        forest = Forest(0)
        self.assertEqual(forest.size(), 0)
        self.assertEqual(forest.edge_count, 0)

    def test_set_and_get_value(self):
        forest = Forest(3)
        forest.set_value(1, 42)
        self.assertEqual(forest.get_value(1), 42)
        forest.set_value(1, -7)
        self.assertEqual(forest.get_value(1), -7)

    def test_set_value_rejects_non_int(self):
        forest = Forest(1)
        with self.assertRaises(ArgErro):
            forest.set_value(0, 1.5)
        with self.assertRaises(ArgErro):
            forest.set_value(0, True)

    def test_negative_size_rejected(self):
        with self.assertRaises(ArgErro):
            Forest(-1)

    def test_unknown_node_rejected(self):
        forest = Forest(2)
        with self.assertRaises(UnknownNodeErro):
            forest.get_value(2)
        with self.assertRaises(UnknownNodeErro):
            forest.get_value(-1)


class TestConnectivity(unittest.TestCase):
    def test_single_node_self_connected(self):
        forest = Forest(3)
        self.assertTrue(forest.connected(0, 0))

    def test_path_components_initially_disconnected(self):
        forest = Forest(4)
        self.assertFalse(forest.connected(0, 1))
        self.assertFalse(forest.connected(2, 3))

    def test_link_connects_two_nodes(self):
        forest = Forest(3)
        forest.link(0, 1)
        self.assertTrue(forest.connected(0, 1))
        self.assertTrue(forest.has_edge(0, 1))
        self.assertEqual(forest.edge_count, 1)

    def test_link_connects_chain(self):
        forest = Forest(4)
        forest.link(0, 1)
        forest.link(1, 2)
        forest.link(2, 3)
        self.assertTrue(forest.connected(0, 3))
        self.assertEqual(forest.edge_count, 3)

    def test_link_rejects_cycle(self):
        forest = Forest(3)
        forest.link(0, 1)
        forest.link(1, 2)
        with self.assertRaises(LinkErro):
            forest.link(0, 2)

    def test_link_rejects_self_loop(self):
        forest = Forest(2)
        with self.assertRaises(LinkErro):
            forest.link(0, 0)


class TestCut(unittest.TestCase):
    def test_cut_makes_disconnected(self):
        forest = Forest(3)
        forest.link(0, 1)
        forest.link(1, 2)
        forest.cut(1, 2)
        self.assertFalse(forest.connected(1, 2))
        self.assertTrue(forest.connected(0, 1))
        self.assertEqual(forest.edge_count, 1)

    def test_cut_missing_edge_rejected(self):
        forest = Forest(3)
        forest.link(0, 1)
        with self.assertRaises(CutErro):
            forest.cut(1, 2)

    def test_cut_self_loop_rejected(self):
        forest = Forest(2)
        with self.assertRaises(CutErro):
            forest.cut(0, 0)


class TestPathAggregates(unittest.TestCase):
    def setUp(self):
        self.forest = Forest(5)
        self.forest.link(0, 1)
        self.forest.link(1, 2)
        self.forest.link(2, 3)
        self.forest.link(3, 4)
        for node, value in enumerate([3, 1, 4, 1, 5]):
            self.forest.set_value(node, value)

    def test_path_sequence(self):
        self.assertEqual(self.forest.path(0, 4), [0, 1, 2, 3, 4])
        self.assertEqual(self.forest.path(3, 1), [3, 2, 1])

    def test_path_of_single_node(self):
        self.assertEqual(self.forest.path(2, 2), [2])

    def test_path_sum(self):
        self.assertEqual(self.forest.path_sum(0, 4), 14)
        self.assertEqual(self.forest.path_sum(1, 3), 6)

    def test_path_min_max(self):
        self.assertEqual(self.forest.path_min(0, 4), 1)
        self.assertEqual(self.forest.path_max(0, 4), 5)

    def test_path_of_single_node_aggregates(self):
        self.assertEqual(self.forest.path_sum(2, 2), 4)
        self.assertEqual(self.forest.path_min(2, 2), 4)
        self.assertEqual(self.forest.path_max(2, 2), 4)

    def test_disconnected_path_is_empty(self):
        forest = Forest(2)
        self.assertEqual(forest.path(0, 1), [])

    def test_aggregates_on_disconnected_rejected(self):
        forest = Forest(2)
        with self.assertRaises(LinkErro):
            forest.path_sum(0, 1)
        with self.assertRaises(LinkErro):
            forest.path_min(0, 1)
        with self.assertRaises(LinkErro):
            forest.path_max(0, 1)


class TestErrorHierarchy(unittest.TestCase):
    def test_errors_share_base(self):
        self.assertTrue(issubclass(UnknownNodeErro, Erro))
        self.assertTrue(issubclass(LinkErro, Erro))
        self.assertTrue(issubclass(CutErro, Erro))
        self.assertTrue(issubclass(ArgErro, Erro))


if __name__ == "__main__":
    unittest.main()
