"""基线测试：锁住改造前 HeapMerge 的现状行为。

这些用例描述的是当前"整体搬迁"实现对外可见的事实，改造后必须继续成立，
因此本文件一字不得修改。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meldset.merge import (
    HeapMerge,
    MeldError,
    UnknownElementError,
    UnknownSetError,
)


class TestMakeAndSize(unittest.TestCase):
    def test_empty_set_size_zero(self):
        hm = HeapMerge()
        a = hm.make_set()
        self.assertEqual(hm.size_of(a), 0)

    def test_make_set_with_elements(self):
        hm = HeapMerge()
        a = hm.make_set([1, 2, 3])
        self.assertEqual(hm.size_of(a), 3)

    def test_make_set_dedups_elements(self):
        hm = HeapMerge()
        a = hm.make_set([5, 5, 5, 6])
        self.assertEqual(hm.size_of(a), 2)


class TestUnionBasics(unittest.TestCase):
    def test_union_returns_new_handle_and_sums_size(self):
        hm = HeapMerge()
        a = hm.make_set([1, 2])
        b = hm.make_set([3, 4, 5])
        merged = hm.union_sets(a, b)
        self.assertEqual(hm.size_of(merged), 5)

    def test_old_handles_invalid_after_union(self):
        hm = HeapMerge()
        a = hm.make_set([1])
        b = hm.make_set([2])
        merged = hm.union_sets(a, b)
        with self.assertRaises(UnknownSetError):
            hm.size_of(a)
        with self.assertRaises(UnknownSetError):
            hm.size_of(b)

    def test_overlapping_elements_merge_once(self):
        hm = HeapMerge()
        a = hm.make_set([1, 2, 3])
        b = hm.make_set([3, 4])
        merged = hm.union_sets(a, b)
        self.assertEqual(hm.size_of(merged), 4)
        self.assertEqual(hm.query(merged, 3), {})

    def test_union_with_empty_set(self):
        hm = HeapMerge()
        a = hm.make_set([7, 8])
        b = hm.make_set()
        merged = hm.union_sets(a, b)
        self.assertEqual(hm.size_of(merged), 2)
        self.assertEqual(hm.query(merged, 7), {})


class TestQueryAndAttr(unittest.TestCase):
    def test_query_missing_element_raises(self):
        hm = HeapMerge()
        a = hm.make_set([1, 2])
        with self.assertRaises(UnknownElementError):
            hm.query(a, 99)

    def test_set_attr_then_query(self):
        hm = HeapMerge()
        a = hm.make_set([1, 2])
        hm.set_attr(a, 1, "color", "red")
        self.assertEqual(hm.query(a, 1), {"color": "red"})

    def test_query_returns_copy(self):
        hm = HeapMerge()
        a = hm.make_set([1])
        hm.set_attr(a, 1, "k", 10)
        snapshot = hm.query(a, 1)
        snapshot["k"] = 999
        self.assertEqual(hm.query(a, 1), {"k": 10})

    def test_set_attr_missing_element_raises(self):
        hm = HeapMerge()
        a = hm.make_set([1])
        with self.assertRaises(UnknownElementError):
            hm.set_attr(a, 2, "k", 1)

    def test_attr_survives_union(self):
        hm = HeapMerge()
        a = hm.make_set([1])
        hm.set_attr(a, 1, "tag", "left")
        b = hm.make_set([2])
        hm.set_attr(b, 2, "tag", "right")
        merged = hm.union_sets(a, b)
        self.assertEqual(hm.query(merged, 1), {"tag": "left"})
        self.assertEqual(hm.query(merged, 2), {"tag": "right"})

    def test_overlap_right_wins_on_union(self):
        # 朴素实现先搬 a 再搬 b，重叠元素以 b 的属性为准（现状行为）。
        hm = HeapMerge()
        a = hm.make_set([1])
        hm.set_attr(a, 1, "src", "a")
        b = hm.make_set([1])
        hm.set_attr(b, 1, "src", "b")
        merged = hm.union_sets(a, b)
        self.assertEqual(hm.query(merged, 1), {"src": "b"})


class TestRemoveAndErrors(unittest.TestCase):
    def test_remove_set_then_query_fails(self):
        hm = HeapMerge()
        a = hm.make_set([1, 2])
        hm.remove_set(a)
        with self.assertRaises(UnknownSetError):
            hm.size_of(a)

    def test_remove_set_does_not_touch_others(self):
        hm = HeapMerge()
        a = hm.make_set([1])
        b = hm.make_set([2, 3])
        hm.remove_set(a)
        self.assertEqual(hm.size_of(b), 2)

    def test_errors_share_base_class(self):
        self.assertTrue(issubclass(UnknownSetError, MeldError))
        self.assertTrue(issubclass(UnknownElementError, MeldError))

    def test_unknown_handle_raises(self):
        hm = HeapMerge()
        with self.assertRaises(UnknownSetError):
            hm.query(424242, 1)


class TestDeterminism(unittest.TestCase):
    def test_fixed_sequence_repeatable(self):
        def run():
            hm = HeapMerge()
            a = hm.make_set([1, 2, 3])
            b = hm.make_set([3, 4])
            hm.set_attr(a, 1, "w", 5)
            m = hm.union_sets(a, b)
            c = hm.make_set([4, 5, 6])
            m2 = hm.union_sets(m, c)
            return hm.size_of(m2), hm.query(m2, 1)

        self.assertEqual(run(), run())


if __name__ == "__main__":
    unittest.main()
