"""朴素通配符匹配的基线行为测试。

锁住改造前的现状: 完全匹配的判定口径、星号吃掉长度的确定口径、相邻星号
合并、边界情形, 以及异常基类与非法输入拒绝。本文件在改造后一字不许改,
且必须一直全绿。
"""

import unittest

from wildcard import (
    Erro,
    NaiveWildcard,
    NoMatchError,
    PatternError,
    TypeMismatchError,
    star_lengths,
)


class TestMatch(unittest.TestCase):
    def test_empty_pattern_empty_text(self):
        self.assertTrue(NaiveWildcard("", "").matches())

    def test_empty_pattern_nonempty_text(self):
        self.assertFalse(NaiveWildcard("abc", "").matches())

    def test_question_marks_exactly_one(self):
        self.assertTrue(NaiveWildcard("abc", "a?c").matches())
        self.assertFalse(NaiveWildcard("ac", "a?c").matches())
        self.assertFalse(NaiveWildcard("abbc", "a?c").matches())

    def test_star_matches_any_length(self):
        self.assertTrue(NaiveWildcard("", "*").matches())
        self.assertTrue(NaiveWildcard("abcdef", "*").matches())
        self.assertTrue(NaiveWildcard("abc", "a*c").matches())
        self.assertTrue(NaiveWildcard("ac", "a*c").matches())

    def test_all_stars(self):
        self.assertTrue(NaiveWildcard("", "***").matches())
        self.assertTrue(NaiveWildcard("xyz", "*").matches())

    def test_literal_only(self):
        self.assertTrue(NaiveWildcard("abc", "abc").matches())
        self.assertFalse(NaiveWildcard("abc", "abd").matches())
        self.assertFalse(NaiveWildcard("ab", "abc").matches())

    def test_star_at_edges(self):
        self.assertTrue(NaiveWildcard("abcdef", "*def").matches())
        self.assertTrue(NaiveWildcard("abcdef", "abc*").matches())
        self.assertFalse(NaiveWildcard("abcdef", "*xyz").matches())


class TestStarLengths(unittest.TestCase):
    def test_single_star_minimal(self):
        self.assertEqual(NaiveWildcard("axybzc", "a*b*c").star_lengths(), (2, 1))

    def test_leading_star_greedy_rest(self):
        self.assertEqual(NaiveWildcard("abcdef", "*def").star_lengths(), (3,))

    def test_trailing_star(self):
        self.assertEqual(NaiveWildcard("abcdef", "abc*").star_lengths(), (3,))

    def test_only_star(self):
        self.assertEqual(NaiveWildcard("abcdef", "*").star_lengths(), (6,))

    def test_all_stars_collapse_to_one(self):
        self.assertEqual(NaiveWildcard("xyz", "***").star_lengths(), (3,))

    def test_empty_text_with_star(self):
        self.assertEqual(NaiveWildcard("", "*").star_lengths(), (0,))

    def test_module_level_independent(self):
        self.assertEqual(star_lengths("a*b*c", "axybzc"), (2, 1))
        self.assertEqual(star_lengths("*", "abcdef"), (6,))

    def test_star_count_after_merge(self):
        self.assertEqual(NaiveWildcard("", "*a**b*").star_count(), 3)
        self.assertEqual(NaiveWildcard("", "abc").star_count(), 0)

    def test_no_match_raises(self):
        with self.assertRaises(NoMatchError):
            NaiveWildcard("abc", "a*d").star_lengths()
        with self.assertRaises(NoMatchError):
            NaiveWildcard("abc", "x*").star_lengths()


class TestBoundaries(unittest.TestCase):
    def test_empty_text_nonempty_pattern(self):
        self.assertFalse(NaiveWildcard("", "a").matches())
        self.assertTrue(NaiveWildcard("", "*").matches())
        self.assertTrue(NaiveWildcard("", "**").matches())

    def test_nonempty_text_empty_pattern(self):
        self.assertFalse(NaiveWildcard("a", "").matches())

    def test_question_and_star_mix(self):
        self.assertTrue(NaiveWildcard("abcde", "?*?").matches())
        self.assertFalse(NaiveWildcard("a", "?*?").matches())

    def test_deterministic_repeat(self):
        w = NaiveWildcard("axybzc", "a*b*c")
        first = w.star_lengths()
        for _ in range(5):
            self.assertEqual(w.star_lengths(), first)


class TestValidation(unittest.TestCase):
    def test_type_mismatch(self):
        with self.assertRaises(TypeMismatchError):
            NaiveWildcard(1, "a")
        with self.assertRaises(TypeMismatchError):
            NaiveWildcard("a", None)

    def test_pattern_bad_char(self):
        with self.assertRaises(PatternError):
            NaiveWildcard("a", "a[b]")

    def test_all_errors_share_base(self):
        for exc in (TypeMismatchError, PatternError, NoMatchError):
            self.assertTrue(issubclass(exc, Erro))
            self.assertTrue(issubclass(exc, Exception))

    def test_properties(self):
        w = NaiveWildcard("abc", "a*c")
        self.assertEqual(w.text, "abc")
        self.assertEqual(w.pattern, "a*c")


if __name__ == "__main__":
    unittest.main()
