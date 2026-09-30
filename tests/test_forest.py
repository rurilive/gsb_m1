"""基线测试：锁住改造前 PersistentDSU 的现状行为。

这些用例描述的是当前"每次合并整份拷贝父指针、按版本取整份快照"实现对外
可见的事实，改造后必须继续成立，因此本文件一字不得修改。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pdsu.forest import (
    DsuInputError,
    Erro,
    PersistentDSU,
    UnknownElemError,
)


def build(n, labels=None):
    return PersistentDSU(n, labels)


class TestVersions(unittest.TestCase):
    def test_version_zero_alive(self):
        d = build(4, list("abcd"))
        self.assertEqual(d.version_count(), 1)
        self.assertEqual(d.merge_count(), 0)
        for name in "abcd":
            self.assertTrue(d.connected(0, name, name))
            self.assertEqual(d.size(0, name), 1)
        self.assertEqual(d.groups(0), [["a"], ["b"], ["c"], ["d"]])

    def test_empty_forest(self):
        d = build(0)
        self.assertEqual(d.version_count(), 1)
        self.assertEqual(d.merge_count(), 0)
        self.assertEqual(d.groups(0), [])
        self.assertEqual(d.group_count(0), 0)

    def test_single_element(self):
        d = build(1, ["solo"])
        self.assertTrue(d.connected(0, "solo", "solo"))
        self.assertEqual(d.representative(0, "solo"), 0)
        self.assertEqual(d.size(0, "solo"), 1)
        self.assertEqual(d.members(0, "solo"), ["solo"])
        self.assertEqual(d.groups(0), [["solo"]])

    def test_default_labels_are_strings(self):
        d = build(3)
        self.assertEqual(d.members(0, "0"), ["0"])
        self.assertEqual(d.members(0, "2"), ["2"])


class TestMergeRule(unittest.TestCase):
    def test_smaller_name_becomes_static(self):
        d = build(4, list("abcd"))
        v1 = d.union(0, "a", "b")
        self.assertEqual(v1, 1)
        self.assertEqual(d.parent_of(v1, "b"), 0)
        self.assertEqual(d.representative(v1, "b"), 0)
        self.assertEqual(d.size(v1, "a"), 2)
        self.assertEqual(d.merge_count(), 1)

    def test_argument_order_does_not_matter(self):
        left = build(4, list("abcd"))
        right = build(4, list("abcd"))
        lv = left.union(0, "a", "b")
        rv = right.union(0, "b", "a")
        self.assertEqual(lv, rv)
        for name in "abcd":
            self.assertEqual(left.parent_of(lv, name), right.parent_of(rv, name))

    def test_non_merge_returns_same_version(self):
        d = build(4, list("abcd"))
        v1 = d.union(0, "a", "b")
        v2 = d.union(v1, "a", "b")
        v3 = d.union(v1, "b", "a")
        self.assertEqual(v2, v1)
        self.assertEqual(v3, v1)
        self.assertEqual(d.version_count(), 2)
        self.assertEqual(d.merge_count(), 1)

    def test_old_version_untouched(self):
        d = build(4, list("abcd"))
        v1 = d.union(0, "a", "b")
        v2 = d.union(v1, "c", "d")
        self.assertEqual(d.parent_of(0, "b"), 1)
        self.assertEqual(d.parent_of(v1, "d"), 3)
        self.assertEqual(d.parent_of(v2, "d"), 2)
        self.assertEqual(d.parent_of(v1, "b"), 0)

    def test_branch_from_old_version(self):
        d = build(4, list("abcd"))
        v1 = d.union(0, "a", "b")
        v2 = d.union(v1, "c", "d")
        v3 = d.union(v1, "b", "c")
        self.assertEqual((v1, v2, v3), (1, 2, 3))
        self.assertTrue(d.connected(v2, "c", "d"))
        self.assertFalse(d.connected(v2, "a", "d"))
        self.assertTrue(d.connected(v3, "a", "c"))
        self.assertFalse(d.connected(v3, "a", "d"))
        self.assertEqual(d.size(v3, "a"), 3)
        self.assertEqual(d.size(v3, "d"), 1)
        self.assertEqual(d.size(v2, "a"), 2)


class TestQueries(unittest.TestCase):
    def test_size_and_groups_after_merges(self):
        d = build(5, list("abcde"))
        v1 = d.union(0, "a", "b")
        v2 = d.union(v1, "c", "d")
        v3 = d.union(v2, "b", "c")
        self.assertEqual(d.size(v1, "a"), 2)
        self.assertEqual(d.size(v2, "c"), 2)
        self.assertEqual(d.size(v3, "a"), 4)
        self.assertEqual(d.members(v3, "d"), ["a", "b", "c", "d"])
        self.assertEqual(d.groups(v3), [["a", "b", "c", "d"], ["e"]])
        self.assertEqual(d.group_count(v3), 2)

    def test_members_returns_independent_copy(self):
        d = build(3, list("abc"))
        v1 = d.union(0, "a", "b")
        snap = d.members(v1, "a")
        snap.append("z")
        self.assertEqual(d.members(v1, "a"), ["a", "b"])

    def test_groups_returns_independent_copy(self):
        d = build(2, list("ab"))
        snap = d.groups(0)
        snap.append(["z"])
        self.assertEqual(d.groups(0), [["a"], ["b"]])


class TestValidation(unittest.TestCase):
    def test_negative_size_rejected(self):
        with self.assertRaises(DsuInputError):
            build(-1)

    def test_label_count_mismatch_rejected(self):
        with self.assertRaises(DsuInputError):
            build(3, ["a", "b"])

    def test_empty_label_rejected(self):
        with self.assertRaises(DsuInputError):
            build(2, ["a", ""])

    def test_non_string_label_rejected(self):
        with self.assertRaises(DsuInputError):
            build(2, ["a", 7])

    def test_unknown_element_rejected(self):
        d = build(2, list("ab"))
        with self.assertRaises(UnknownElemError):
            d.size(0, "zz")
        with self.assertRaises(UnknownElemError):
            d.connected(0, "a", "zz")

    def test_bad_version_rejected(self):
        d = build(2, list("ab"))
        with self.assertRaises(DsuInputError):
            d.size(5, "a")
        with self.assertRaises(DsuInputError):
            d.connected(-1, "a", "b")

    def test_connected_on_empty_forest_rejected(self):
        d = build(0)
        with self.assertRaises(UnknownElemError):
            d.connected(0, "a", "b")

    def test_errors_share_base_class(self):
        self.assertTrue(issubclass(DsuInputError, Erro))
        self.assertTrue(issubclass(UnknownElemError, Erro))


class TestDeterminism(unittest.TestCase):
    def test_fixed_input_repeatable(self):
        def run():
            d = build(6, list("abcdef"))
            v1 = d.union(0, "a", "b")
            v2 = d.union(v1, "c", "d")
            v3 = d.union(v2, "b", "c")
            v4 = d.union(v1, "e", "f")
            return (
                d.groups(v4),
                d.size(v4, "a"),
                d.connected(v4, "e", "a"),
                d.parent_of(v3, "d"),
                d.version_count(),
            )

        self.assertEqual(run(), run())


if __name__ == "__main__":
    unittest.main()
