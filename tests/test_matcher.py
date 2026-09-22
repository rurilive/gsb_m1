"""匹配与搜索现有行为的锁定测试。"""

import unittest

import rexflow
from rexflow import Match, Pattern, PatternError, compile


class TestFullmatch(unittest.TestCase):
    def test_plain_literals(self):
        self.assertTrue(compile("abc").fullmatch("abc"))
        self.assertFalse(compile("abc").fullmatch("abd"))
        self.assertFalse(compile("abc").fullmatch("ab"))
        self.assertFalse(compile("abc").fullmatch("abcd"))

    def test_star_matches_zero_or_more(self):
        pat = compile("ab*c")
        self.assertTrue(pat.fullmatch("ac"))
        self.assertTrue(pat.fullmatch("abc"))
        self.assertTrue(pat.fullmatch("abbbc"))
        self.assertFalse(pat.fullmatch("abbb"))

    def test_empty_pattern_only_matches_empty_text(self):
        self.assertTrue(compile("").fullmatch(""))
        self.assertFalse(compile("").fullmatch("x"))

    def test_star_backtracks_when_needed(self):
        # a* 先吃光两个 a，发现后面还有 a 要吃，再吐一个回来
        self.assertTrue(compile("a*ab").fullmatch("aab"))
        self.assertFalse(compile("a*ab").fullmatch("aa"))
        self.assertTrue(compile("a*ab").fullmatch("ab"))

    def test_text_must_be_str(self):
        with self.assertRaises(TypeError):
            compile("a").fullmatch(b"a")


class TestSearch(unittest.TestCase):
    def test_finds_match_inside_text(self):
        got = compile("ab*c").search("xxabbc yy")
        self.assertEqual(got.span(), (2, 6))

    def test_no_match_returns_none(self):
        self.assertIsNone(compile("ab*c").search("nothing here"))

    def test_greedy_takes_longest_run(self):
        self.assertEqual(compile("a*").search("aaab").span(), (0, 3))

    def test_empty_match_wins_at_leftmost_position(self):
        # a* 在 0 号位就能空匹配，哪怕后头有更长的 a 串也是它
        self.assertEqual(compile("a*").search("baa").span(), (0, 0))

    def test_match_at_tail(self):
        self.assertEqual(compile("c").search("abc").span(), (2, 3))

    def test_empty_text(self):
        self.assertEqual(compile("a*").search("").span(), (0, 0))

    def test_match_object(self):
        got = compile("bb*").search("abba ")
        self.assertIsInstance(got, Match)
        self.assertEqual(got.group(), "bb")
        self.assertEqual(got.start(), 1)
        self.assertEqual(got.end(), 3)
        self.assertEqual(got.span(), (1, 3))

    def test_search_text_must_be_str(self):
        with self.assertRaises(TypeError):
            compile("a").search(b"a")


class TestPatternObject(unittest.TestCase):
    def test_pattern_attribute_kept(self):
        self.assertEqual(compile("ab*").pattern, "ab*")

    def test_bad_pattern_raises_at_compile_time(self):
        with self.assertRaises(PatternError):
            Pattern("*ab")

    def test_module_level_helpers(self):
        self.assertTrue(rexflow.fullmatch("ab*", "abb"))
        self.assertEqual(rexflow.search("a*", "zaa").span(), (0, 0))


if __name__ == "__main__":
    unittest.main()
