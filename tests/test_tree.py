"""BrutePalTree 现状行为的锁定测试（基线，一字不改且必须全绿）。

锁的是一段固定文本上枚举子串当场判断的结果：子串回文判断、全部回文
子串的收集顺序与重复、某位置为结尾的回文个数、某个回文是否出现，以及
非法参数必须 fail fast、异常统一挂在基类下。
"""

import unittest

from paltree.tree import (
    BrutePalTree,
    IllegalArgument,
    IndexOutOfRange,
    NotASubstring,
    PalTreeError,
)

# 固定文本：含重复回文，便于锁住不去重的收集口径。
FIXED_TEXT = "ababa"


def build():
    return BrutePalTree(FIXED_TEXT)


class TestBrutePalTreeText(unittest.TestCase):
    def test_text_read_back(self):
        t = build()
        self.assertEqual(t.text, FIXED_TEXT)
        self.assertEqual(len(t), 5)

    def test_rejects_non_string_text(self):
        with self.assertRaises(PalTreeError):
            BrutePalTree(123)
        with self.assertRaises(IllegalArgument):
            BrutePalTree(None)


class TestIsPal(unittest.TestCase):
    def test_true_cases(self):
        t = build()
        for s in ("a", "b", "aba", "bab", "ababa"):
            self.assertTrue(t.is_pal(s), s)

    def test_false_cases(self):
        t = build()
        for s in ("ab", "ba", "abab", "baba"):
            self.assertFalse(t.is_pal(s), s)

    def test_not_a_substring(self):
        t = build()
        with self.assertRaises(NotASubstring):
            t.is_pal("abc")
        with self.assertRaises(PalTreeError):
            t.is_pal("zzz")

    def test_empty_rejected(self):
        t = build()
        with self.assertRaises(IllegalArgument):
            t.is_pal("")

    def test_non_string_rejected(self):
        t = build()
        with self.assertRaises(IllegalArgument):
            t.is_pal(5)


class TestPalindromicSubstrings(unittest.TestCase):
    def test_full_collection_with_repeats(self):
        t = build()
        # 按起点、再由短到长；同串出现几次收几次。
        self.assertEqual(
            t.palindromic_substrings(),
            ["a", "aba", "ababa", "b", "bab", "a", "aba", "b", "a"],
        )

    def test_count_matches_length(self):
        t = build()
        self.assertEqual(len(t.palindromic_substrings()), 9)

    def test_single_character_text(self):
        t = BrutePalTree("x")
        self.assertEqual(t.palindromic_substrings(), ["x"])

    def test_all_equal_text(self):
        t = BrutePalTree("aaa")
        self.assertEqual(
            t.palindromic_substrings(),
            ["a", "aa", "aaa", "a", "aa", "a"],
        )


class TestPalCountByEnd(unittest.TestCase):
    def test_every_position(self):
        t = build()
        self.assertEqual([t.pal_count_by_end(i) for i in range(5)], [1, 1, 2, 2, 3])

    def test_single_character(self):
        t = BrutePalTree("x")
        self.assertEqual(t.pal_count_by_end(0), 1)

    def test_all_equal(self):
        t = BrutePalTree("aaaa")
        self.assertEqual([t.pal_count_by_end(i) for i in range(4)], [1, 2, 3, 4])

    def test_out_of_range(self):
        t = build()
        with self.assertRaises(IndexOutOfRange):
            t.pal_count_by_end(5)
        with self.assertRaises(IndexOutOfRange):
            t.pal_count_by_end(-1)

    def test_non_int_rejected(self):
        t = build()
        with self.assertRaises(IllegalArgument):
            t.pal_count_by_end("0")


class TestContainsPal(unittest.TestCase):
    def test_present(self):
        t = build()
        self.assertTrue(t.contains_pal("aba"))
        self.assertTrue(t.contains_pal("ababa"))

    def test_absent_but_valid_palindrome(self):
        t = build()
        self.assertFalse(t.contains_pal("aa"))

    def test_not_a_palindrome_rejected(self):
        t = build()
        with self.assertRaises(IllegalArgument):
            t.contains_pal("ab")

    def test_empty_rejected(self):
        t = build()
        with self.assertRaises(IllegalArgument):
            t.contains_pal("")


class TestExceptionHierarchy(unittest.TestCase):
    def test_all_inherit_base(self):
        for exc in (IllegalArgument, NotASubstring, IndexOutOfRange):
            self.assertTrue(issubclass(exc, PalTreeError))
        self.assertTrue(issubclass(PalTreeError, Exception))


if __name__ == "__main__":
    unittest.main()
