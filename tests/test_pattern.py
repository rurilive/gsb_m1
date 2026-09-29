"""基线测试：锁住 regexlib 改造前的字面匹配现状行为。

这份文件是改造前的既成事实，改造之后必须原样保留且继续全绿。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from regexlib import LiteralPat, RegexError, literal_match, literal_search


class TestLiteralMatch(unittest.TestCase):
    def test_match_requires_whole_equal(self):
        pat = LiteralPat("abc")
        self.assertTrue(pat.match("abc"))
        self.assertFalse(pat.match("xabc"))
        self.assertFalse(pat.match("abcx"))
        self.assertFalse(pat.match("ab"))

    def test_match_is_case_sensitive(self):
        self.assertFalse(LiteralPat("abc").match("ABC"))

    def test_search_finds_substring(self):
        pat = LiteralPat("abc")
        self.assertTrue(pat.search("xxabcxx"))
        self.assertTrue(pat.search("abc"))
        self.assertFalse(pat.search("abx"))

    def test_search_accepts_longer_input(self):
        self.assertTrue(LiteralPat("ab").search("zzabzz"))

    def test_finditer_reports_all_non_overlapping(self):
        pat = LiteralPat("ab")
        self.assertEqual(pat.finditer("ababab"), [(0, 2), (2, 4), (4, 6)])
        self.assertEqual(pat.finditer("abababab"), [(0, 2), (2, 4), (4, 6), (6, 8)])

    def test_finditer_skips_overlaps(self):
        # 非重叠口径：aa 在 aaaa 里只算两次。
        self.assertEqual(LiteralPat("aa").finditer("aaaa"), [(0, 2), (2, 4)])

    def test_finditer_empty_when_absent(self):
        self.assertEqual(LiteralPat("zz").finditer("abcabc"), [])

    def test_finditer_includes_position_zero(self):
        self.assertEqual(LiteralPat("ab").finditer("abc"), [(0, 2)])

    def test_special_character_is_rejected(self):
        for bad in ["a*b", "a?b", "a|b", "a+b", "a.b", "(a)", "[a]", "a^", "a$"]:
            with self.assertRaises(RegexError):
                LiteralPat(bad)

    def test_empty_pattern_is_literal(self):
        pat = LiteralPat("")
        self.assertTrue(pat.match(""))
        self.assertFalse(pat.match("x"))
        # 空模式在每个下标处都算一次命中。
        self.assertEqual(pat.finditer("ab"), [(0, 0), (1, 1), (2, 2)])

    def test_module_level_helpers(self):
        self.assertTrue(literal_match("abc", "abc"))
        self.assertFalse(literal_match("abc", "xabc"))
        self.assertTrue(literal_search("abc", "xabcx"))
        self.assertFalse(literal_search("abc", "xabx"))


class TestRegexErrorIsValueError(unittest.TestCase):
    def test_regex_error_is_value_error_subclass(self):
        self.assertTrue(issubclass(RegexError, ValueError))

    def test_non_string_pattern_rejected(self):
        with self.assertRaises(RegexError):
            LiteralPat(None)


if __name__ == "__main__":
    unittest.main()
