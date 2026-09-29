"""基线测试:锁住 BruteDict 改造前的现状行为。

这些用例是"改造前"的事实契约,实现迭代时不得修改,必须保持全绿。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aclib.dict import BruteDict, DictError, InvalidPatternError


class TestAddAndPatterns(unittest.TestCase):
    def test_add_keeps_insertion_order(self):
        d = BruteDict()
        d.add("he")
        d.add("she")
        d.add("hers")
        self.assertEqual(d.patterns(), ["he", "she", "hers"])

    def test_add_duplicate_is_ignored(self):
        d = BruteDict()
        d.add("ab")
        d.add("ab")
        self.assertEqual(d.patterns(), ["ab"])

    def test_add_empty_raises(self):
        d = BruteDict()
        with self.assertRaises(InvalidPatternError):
            d.add("")

    def test_add_non_string_raises(self):
        d = BruteDict()
        with self.assertRaises(InvalidPatternError):
            d.add(123)


class TestCountOccurrences(unittest.TestCase):
    def test_counts_each_pattern(self):
        d = BruteDict()
        d.add("he")
        d.add("she")
        counts = d.count_occurrences("ushers he she")
        self.assertEqual(counts["he"], 3)
        self.assertEqual(counts["she"], 2)

    def test_counts_include_overlaps(self):
        d = BruteDict()
        d.add("aa")
        self.assertEqual(d.count_occurrences("aaaa")["aa"], 3)

    def test_counts_zero_when_absent(self):
        d = BruteDict()
        d.add("zz")
        self.assertEqual(d.count_occurrences("abc")["zz"], 0)

    def test_empty_dict_yields_empty_result(self):
        d = BruteDict()
        self.assertEqual(d.count_occurrences("anything"), {})


class TestFirstMatch(unittest.TestCase):
    def test_first_match_reports_earliest_position(self):
        d = BruteDict()
        d.add("he")
        d.add("she")
        self.assertEqual(d.first_match("ushers"), (1, "she"))

    def test_first_match_none_when_absent(self):
        d = BruteDict()
        d.add("xy")
        self.assertIsNone(d.first_match("abcdef"))

    def test_first_match_tie_prefers_insertion_order(self):
        d = BruteDict()
        d.add("ab")
        d.add("abc")
        self.assertEqual(d.first_match("zabc"), (1, "ab"))


class TestMatchesIn(unittest.TestCase):
    def test_matches_in_lists_all_positions(self):
        d = BruteDict()
        d.add("aa")
        self.assertEqual(d.matches_in("aaaa")["aa"], [0, 1, 2])

    def test_matches_in_multiple_patterns(self):
        d = BruteDict()
        d.add("he")
        d.add("she")
        got = d.matches_in("ushers he")
        self.assertEqual(got["he"], [2, 7])
        self.assertEqual(got["she"], [1])


class TestErrors(unittest.TestCase):
    def test_invalid_pattern_error_is_value_error(self):
        self.assertTrue(issubclass(InvalidPatternError, ValueError))

    def test_invalid_pattern_error_is_dict_error(self):
        self.assertTrue(issubclass(InvalidPatternError, DictError))

    def test_dict_error_is_exception(self):
        self.assertTrue(issubclass(DictError, Exception))


if __name__ == "__main__":
    unittest.main()
