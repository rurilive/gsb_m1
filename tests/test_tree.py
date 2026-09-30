"""基线测试：锁住改造前 balancedbst.tree.BalancedBST 的现状行为。

这些断言描述的是「当前朴素实现的事实」，不是「最终应当的样子」：
  - 这是一棵普通二叉搜索树，插入按值大小递归下降，重复键照挂不合并；
  - 删除找中序后继顶替，再删后继原位置；
  - 有序或倒序插入会退化成一条链，树高与元素个数同阶；
  - 单次操作的结点访问数正比于当时的树高，有序插入后线性增长；
  - 非法值类型、空树取极值、删除不存在的键分别抛对应异常且都继承基类；
  - 同一个实例反复调用不残留痕迹，固定输入重复跑结果一致。

改造时本文件一字不得修改，且必须保持全绿。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from balancedbst.tree import (  # noqa: E402
    BalancedBST,
    BalancedBSTError,
    EmptyTreeError,
    KeyMissingError,
    ValueTypeError,
)


class TestBaselineQueries(unittest.TestCase):
    def setUp(self):
        self.t = BalancedBST()
        for v in (50, 30, 70, 20, 40, 60, 80):
            self.t.add(v)

    def test_size_and_empty(self):
        self.assertFalse(self.t.is_empty())
        self.assertEqual(self.t.size(), 7)
        self.assertTrue(BalancedBST().is_empty())

    def test_contains_and_find(self):
        self.assertTrue(self.t.contains(40))
        self.assertFalse(self.t.contains(41))
        self.assertEqual(self.t.find(60), 60)

    def test_inorder_is_sorted(self):
        self.assertEqual(self.t.inorder(), [20, 30, 40, 50, 60, 70, 80])

    def test_min_max(self):
        self.assertEqual(self.t.min(), 20)
        self.assertEqual(self.t.max(), 80)

    def test_height_on_balanced_shape(self):
        # 完全对称的七结点树，高为 3
        self.assertEqual(self.t.height(), 3)


class TestNaiveDuplicates(unittest.TestCase):
    def test_duplicates_are_kept(self):
        t = BalancedBST()
        for v in (5, 5, 5, 3):
            t.add(v)
        self.assertEqual(t.size(), 4)
        self.assertEqual(t.inorder(), [3, 5, 5, 5])

    def test_contains_duplicate_key(self):
        t = BalancedBST()
        t.add(7)
        t.add(7)
        self.assertTrue(t.contains(7))
        t.remove(7)
        self.assertTrue(t.contains(7))
        self.assertEqual(t.size(), 1)


class TestNaiveDeletion(unittest.TestCase):
    def test_remove_leaf(self):
        t = BalancedBST()
        for v in (5, 3, 8):
            t.add(v)
        self.assertEqual(t.remove(3), 2)
        self.assertEqual(t.inorder(), [5, 8])
        self.assertFalse(t.contains(3))

    def test_remove_node_with_one_child(self):
        t = BalancedBST()
        for v in (5, 3, 8, 1):
            t.add(v)
        t.remove(3)
        self.assertEqual(t.inorder(), [1, 5, 8])

    def test_remove_node_with_two_children(self):
        t = BalancedBST()
        for v in (50, 30, 70, 20, 40, 60, 80):
            t.add(v)
        t.remove(30)  # 有两个孩子，用中序后继 40 顶替
        self.assertEqual(t.inorder(), [20, 40, 50, 60, 70, 80])
        self.assertFalse(t.contains(30))

    def test_remove_root(self):
        t = BalancedBST()
        for v in (5, 3, 8):
            t.add(v)
        t.remove(5)
        self.assertEqual(t.inorder(), [3, 8])

    def test_remove_down_to_empty(self):
        t = BalancedBST()
        for v in (2, 1, 3):
            t.add(v)
        for v in (2, 1, 3):
            t.remove(v)
        self.assertTrue(t.is_empty())
        self.assertEqual(t.height(), 0)
        self.assertEqual(t.inorder(), [])


class TestNaiveDegenerates(unittest.TestCase):
    def test_ascending_insert_makes_a_chain(self):
        t = BalancedBST()
        for v in range(1, 11):
            t.add(v)
        # 升序插入，朴素实现一路往右挂，退化成一条链
        self.assertEqual(t.height(), 10)

    def test_descending_insert_makes_a_chain(self):
        t = BalancedBST()
        for v in range(10, 0, -1):
            t.add(v)
        self.assertEqual(t.height(), 10)

    def test_height_tracks_size_on_ordered_input(self):
        t = BalancedBST()
        for v in range(1, 33):
            t.add(v)
        self.assertEqual(t.height(), t.size())


class TestNaiveProbes(unittest.TestCase):
    def test_probes_grow_with_depth(self):
        t = BalancedBST()
        for v in range(1, 9):
            t.add(v)
        before = t.probes()
        t.contains(8)     # 链上要走到底
        after = t.probes()
        self.assertGreater(after - before, 1)

    def test_ordered_insert_probes_are_linear(self):
        t = BalancedBST()
        for v in range(1, 9):
            t.add(v)
        before = t.probes()
        t.contains(8)
        grown = t.probes() - before
        # 链深 8，查最深的键要走过与元素个数同阶的结点
        self.assertGreaterEqual(grown, 7)

    def test_stats_reports_height_and_probes(self):
        t = BalancedBST()
        t.add(1)
        t.add(2)
        t.add(3)
        st = t.stats()
        self.assertEqual(st["size"], 3)
        self.assertEqual(st["height"], 3)

    def test_stats_is_fresh_dict(self):
        t = BalancedBST()
        t.add(1)
        st = t.stats()
        st["size"] = 999
        self.assertEqual(t.stats()["size"], 1)


class TestBaselineEdges(unittest.TestCase):
    def test_empty_tree_extremum_rejected(self):
        t = BalancedBST()
        with self.assertRaises(EmptyTreeError):
            t.min()
        with self.assertRaises(EmptyTreeError):
            t.max()

    def test_single_node(self):
        t = BalancedBST()
        t.add(42)
        self.assertEqual(t.height(), 1)
        self.assertEqual(t.min(), 42)
        self.assertEqual(t.max(), 42)
        self.assertEqual(t.inorder(), [42])

    def test_empty_inorder(self):
        self.assertEqual(BalancedBST().inorder(), [])


class TestBaselineErrors(unittest.TestCase):
    def test_all_errors_share_base(self):
        for exc in (EmptyTreeError, KeyMissingError, ValueTypeError):
            self.assertTrue(issubclass(exc, BalancedBSTError))

    def test_remove_missing_key_rejected(self):
        t = BalancedBST()
        t.add(5)
        with self.assertRaises(KeyMissingError):
            t.remove(99)

    def test_find_missing_key_rejected(self):
        t = BalancedBST()
        t.add(5)
        with self.assertRaises(KeyMissingError):
            t.find(99)

    def test_bad_value_type_rejected(self):
        t = BalancedBST()
        with self.assertRaises(ValueTypeError):
            t.add("x")
        with self.assertRaises(ValueTypeError):
            t.contains(1.5)


class TestBaselineDeterminism(unittest.TestCase):
    def test_repeat_runs_identical(self):
        def run():
            t = BalancedBST()
            for v in (5, 3, 8, 1, 4, 7, 9, 3):
                t.add(v)
            t.remove(3)
            t.remove(8)
            return (t.inorder(), t.height(), t.min(), t.max(), t.contains(4))

        self.assertEqual(run(), run())

    def test_no_cross_call_residue(self):
        t = BalancedBST()
        t.add(2)
        t.add(1)
        first = t.inorder()
        second = t.inorder()
        self.assertEqual(first, second)
        self.assertEqual(t.size(), 2)


if __name__ == "__main__":
    unittest.main()
