"""diff 与 merge 现有行为的锁定测试。

只覆盖当前已支持的能力：逐位比较两段序列报出差异，以及在两侧都与基线
一致时把改动抄过去。后面新增的编辑脚本、三方逐块合并、冲突标记与策略
注入另开测试文件，不改动本文件。
"""

import unittest

from mergekit import ADD, EQUAL, REMOVE, DiffError
from mergekit import changes_only, diff, ensure_sequence, has_changes, merge, same_list


class TestSequenceValidation(unittest.TestCase):
    def test_list_is_accepted(self):
        self.assertEqual(list(ensure_sequence([1, 2], "left")), [1, 2])

    def test_tuple_is_accepted(self):
        self.assertEqual(list(ensure_sequence((1, 2), "left")), [1, 2])

    def test_string_is_rejected(self):
        with self.assertRaises(DiffError):
            ensure_sequence("abc", "left")

    def test_dict_is_rejected(self):
        with self.assertRaises(DiffError):
            ensure_sequence({"a": 1}, "left")

    def test_none_is_rejected(self):
        with self.assertRaises(DiffError):
            ensure_sequence(None, "left")

    def test_diff_rejects_bad_left(self):
        with self.assertRaises(DiffError):
            diff("abc", [1, 2])

    def test_diff_rejects_bad_right(self):
        with self.assertRaises(DiffError):
            diff([1, 2], 7)


class TestDiffEqual(unittest.TestCase):
    def test_identical_sequences_have_no_changes(self):
        changes = diff([1, 2, 3], [1, 2, 3])
        self.assertFalse(has_changes(changes))
        self.assertEqual(changes_only(changes), [])

    def test_identical_sequences_are_all_equal(self):
        changes = diff(["a", "b"], ["a", "b"])
        self.assertEqual([c.kind for c in changes], [EQUAL, EQUAL])

    def test_two_empty_sequences_are_equal(self):
        changes = diff([], [])
        self.assertFalse(has_changes(changes))


class TestDiffTail(unittest.TestCase):
    def test_longer_right_tail_is_add(self):
        changes = changes_only(diff([1, 2, 3], [1, 2, 3, 4]))
        self.assertEqual(len(changes), 1)
        added = changes[0]
        self.assertEqual(added.kind, ADD)
        self.assertEqual(added.index, 3)
        self.assertEqual(added.right, 4)
        self.assertIsNone(added.left)

    def test_longer_left_tail_is_remove(self):
        changes = changes_only(diff([1, 2, 3, 4], [1, 2, 3]))
        self.assertEqual(len(changes), 1)
        removed = changes[0]
        self.assertEqual(removed.kind, REMOVE)
        self.assertEqual(removed.index, 3)
        self.assertEqual(removed.left, 4)
        self.assertIsNone(removed.right)

    def test_empty_left_against_item_is_add(self):
        changes = changes_only(diff([], [9]))
        self.assertEqual(changes[0].kind, ADD)
        self.assertEqual(changes[0].right, 9)

    def test_item_against_empty_right_is_remove(self):
        changes = changes_only(diff([9], []))
        self.assertEqual(changes[0].kind, REMOVE)
        self.assertEqual(changes[0].left, 9)


class TestDiffPurity(unittest.TestCase):
    def test_inputs_are_not_mutated(self):
        left, right = [1, 2, 3], [1, 2, 3, 4]
        diff(left, right)
        self.assertEqual(left, [1, 2, 3])
        self.assertEqual(right, [1, 2, 3, 4])

    def test_diff_returns_a_list(self):
        self.assertIsInstance(diff([1], [1]), list)


class TestSameList(unittest.TestCase):
    def test_equal_sequences_match(self):
        self.assertTrue(same_list([1, 2], [1, 2]))

    def test_different_length_does_not_match(self):
        self.assertFalse(same_list([1, 2], [1, 2, 3]))

    def test_different_value_does_not_match(self):
        self.assertFalse(same_list([1, 2], [1, 9]))


class TestMergeBaseline(unittest.TestCase):
    def test_all_three_equal_returns_base(self):
        self.assertEqual(merge([1, 2, 3], [1, 2, 3], [1, 2, 3]), [1, 2, 3])

    def test_unchanged_ours_takes_theirs(self):
        base = [1, 2, 3]
        ours = [1, 2, 3]
        theirs = [1, 2, 3, 4]
        self.assertEqual(merge(base, ours, theirs), [1, 2, 3, 4])

    def test_unchanged_theirs_takes_ours(self):
        base = [1, 2, 3]
        ours = [0, 1, 2, 3]
        theirs = [1, 2, 3]
        self.assertEqual(merge(base, ours, theirs), [0, 1, 2, 3])

    def test_result_is_a_list(self):
        self.assertIsInstance(merge([1], [1], [1]), list)

    def test_inputs_are_not_mutated(self):
        base, ours, theirs = [1, 2], [1, 2, 3], [1, 2]
        merge(base, ours, theirs)
        self.assertEqual(base, [1, 2])
        self.assertEqual(ours, [1, 2, 3])
        self.assertEqual(theirs, [1, 2])

    def test_merge_rejects_non_sequence(self):
        with self.assertRaises(DiffError):
            merge([1], [1], "oops")


if __name__ == "__main__":
    unittest.main()
