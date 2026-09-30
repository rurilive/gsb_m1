"""朴素子串统计的现状锁定测试。

这些断言锁的是改造前 SubstringStats 的现有行为，实现改造后必须一字不改地继续全绿。
"""

import unittest

from sufauto.substat import SubstringStats


class TestDistinctCount(unittest.TestCase):
    def test_single_char(self):
        self.assertEqual(SubstringStats("a").distinct_substring_count(), 1)

    def test_all_identical(self):
        self.assertEqual(SubstringStats("aaaa").distinct_substring_count(), 4)

    def test_all_distinct(self):
        # abcde 的全部子串恰好各不重复：n*(n+1)/2 = 15
        self.assertEqual(SubstringStats("abcde").distinct_substring_count(), 15)

    def test_with_repeats(self):
        # abab 的不同子串：a b ab ba aba bab abab 共 7
        self.assertEqual(SubstringStats("abab").distinct_substring_count(), 7)

    def test_empty(self):
        self.assertEqual(SubstringStats("").distinct_substring_count(), 0)


class TestOccurrences(unittest.TestCase):
    def test_count_overlapping(self):
        self.assertEqual(SubstringStats("aaaa").count_occurrences("aa"), 3)

    def test_count_basic(self):
        s = SubstringStats("ababab")
        self.assertEqual(s.count_occurrences("ab"), 3)
        self.assertEqual(s.count_occurrences("aba"), 2)
        self.assertEqual(s.count_occurrences("b"), 3)

    def test_absent(self):
        self.assertEqual(SubstringStats("abc").count_occurrences("d"), 0)

    def test_empty_pattern(self):
        # 空串的出现次数按 len+1 计（每个位置之前都算一次）
        self.assertEqual(SubstringStats("abc").count_occurrences(""), 4)

    def test_whole_string(self):
        self.assertEqual(SubstringStats("hello").count_occurrences("hello"), 1)


class TestContains(unittest.TestCase):
    def test_present_and_absent(self):
        s = SubstringStats("banana")
        self.assertTrue(s.contains("ana"))
        self.assertFalse(s.contains("apple"))

    def test_empty_is_present(self):
        self.assertTrue(SubstringStats("x").contains(""))


class TestLongestRepeated(unittest.TestCase):
    def test_no_repeat(self):
        self.assertEqual(SubstringStats("abcd").longest_repeated_substring(), "")

    def test_basic(self):
        self.assertEqual(SubstringStats("banana").longest_repeated_substring(), "ana")

    def test_all_identical(self):
        self.assertEqual(SubstringStats("aaaa").longest_repeated_substring(), "aaa")

    def test_empty(self):
        self.assertEqual(SubstringStats("").longest_repeated_substring(), "")


class TestDistinctList(unittest.TestCase):
    def test_sorted_and_unique(self):
        got = SubstringStats("aba").distinct_substrings()
        self.assertEqual(got, sorted(set(got)))
        self.assertEqual(len(got), 5)

    def test_empty(self):
        self.assertEqual(SubstringStats("").distinct_substrings(), [])


class TestConstruction(unittest.TestCase):
    def test_non_string_rejected(self):
        with self.assertRaises(TypeError):
            SubstringStats(123)

    def test_text_property(self):
        self.assertEqual(SubstringStats("abc").text, "abc")

    def test_bad_pattern_type(self):
        with self.assertRaises(TypeError):
            SubstringStats("abc").count_occurrences(3)


if __name__ == "__main__":
    unittest.main()
