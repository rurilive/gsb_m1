"""BruteStats 现状行为的锁定测试（改造前基线，一个字都不许改）。

用固定串把当前那套枚举子串的做法所给出的事实逐项钉死：某段是不是回文、
最长回文是谁、回文子串总数、本质不同的回文集合、某个回文出现了多少次，
以及给定中心的最长回文半径。这些数字都是基线实现实际算出来的，任何一次
改动只要动摇了既有对外行为，这里就会红。
"""

import unittest

from manacher.pal import BruteStats, Erro

S = "abaxyzzyxf"


class TestIsPalindrome(unittest.TestCase):
    def setUp(self):
        self.p = BruteStats(S)

    def test_single_char_is_palindrome(self):
        self.assertTrue(self.p.is_palindrome(0, 1))
        self.assertTrue(self.p.is_palindrome(9, 10))
        self.assertTrue(self.p.is_palindrome(2, 3))

    def test_empty_span_is_palindrome(self):
        self.assertTrue(self.p.is_palindrome(3, 3))
        self.assertTrue(self.p.is_palindrome(0, 0))

    def test_true_spans(self):
        self.assertTrue(self.p.is_palindrome(0, 3))   # aba
        self.assertTrue(self.p.is_palindrome(3, 9))   # xyzzyx
        self.assertTrue(self.p.is_palindrome(4, 8))   # yzzy
        self.assertTrue(self.p.is_palindrome(5, 7))   # zz

    def test_false_spans(self):
        self.assertFalse(self.p.is_palindrome(0, 2))  # ab
        self.assertFalse(self.p.is_palindrome(1, 3))  # ba
        self.assertFalse(self.p.is_palindrome(0, 10))


class TestLongestPalindrome(unittest.TestCase):
    def test_mixed(self):
        self.assertEqual(BruteStats(S).longest_palindrome(), "xyzzyx")
        self.assertEqual(BruteStats(S).longest_palindrome_len(), 6)

    def test_tie_takes_smaller_start(self):
        p = BruteStats("abab")
        self.assertEqual(p.longest_palindrome(), "aba")
        self.assertEqual(p.longest_palindrome_len(), 3)

    def test_all_equal(self):
        self.assertEqual(BruteStats("aaa").longest_palindrome(), "aaa")
        self.assertEqual(BruteStats("aaa").longest_palindrome_len(), 3)

    def test_empty(self):
        self.assertEqual(BruteStats("").longest_palindrome(), "")
        self.assertEqual(BruteStats("").longest_palindrome_len(), 0)


class TestCountPalindromes(unittest.TestCase):
    def test_mixed(self):
        self.assertEqual(BruteStats(S).count_palindromes(), 14)

    def test_all_equal_counts_every_span(self):
        self.assertEqual(BruteStats("aaa").count_palindromes(), 6)

    def test_single_char(self):
        self.assertEqual(BruteStats("a").count_palindromes(), 1)

    def test_empty(self):
        self.assertEqual(BruteStats("").count_palindromes(), 0)


class TestDistinctPalindromes(unittest.TestCase):
    def test_mixed_set(self):
        p = BruteStats(S)
        self.assertEqual(
            p.distinct_palindromes(),
            {"a", "b", "f", "x", "y", "z", "zz", "aba", "yzzy", "xyzzyx"},
        )
        self.assertEqual(p.count_distinct_palindromes(), 10)

    def test_all_equal(self):
        p = BruteStats("aaa")
        self.assertEqual(p.distinct_palindromes(), {"a", "aa", "aaa"})
        self.assertEqual(p.count_distinct_palindromes(), 3)

    def test_empty(self):
        p = BruteStats("")
        self.assertEqual(p.distinct_palindromes(), set())
        self.assertEqual(p.count_distinct_palindromes(), 0)


class TestOccurrence(unittest.TestCase):
    def test_overlapping_all_equal(self):
        p = BruteStats("aaa")
        self.assertEqual(p.occurrence_count("a"), 3)
        self.assertEqual(p.occurrence_count("aa"), 2)
        self.assertEqual(p.occurrence_count("aaa"), 1)

    def test_mixed(self):
        p = BruteStats("abab")
        self.assertEqual(p.occurrence_count("a"), 2)
        self.assertEqual(p.occurrence_count("aba"), 1)
        self.assertEqual(p.occurrence_count("bab"), 1)

    def test_present_once(self):
        self.assertEqual(BruteStats(S).occurrence_count("xyzzyx"), 1)


class TestEachCenterMax(unittest.TestCase):
    def test_radius_table_mixed(self):
        got = [BruteStats(S).each_center_max(k) for k in range(2 * len(S) + 1)]
        self.assertEqual(
            got,
            [1, 0, 2, 0, 1, 0, 1, 0, 1, 0, 1, 3, 1, 0, 1, 0, 1, 0, 1, 0, 1],
        )

    def test_radius_table_all_equal(self):
        p = BruteStats("aaa")
        self.assertEqual([p.each_center_max(k) for k in range(7)], [1, 1, 2, 1, 1, 0, 1])

    def test_center_numbering(self):
        self.assertEqual(BruteStats(S).each_center_max(11), 3)   # 整个串正中
        self.assertEqual(BruteStats(S).each_center_max(0), 1)    # 首个字符中心
        self.assertEqual(BruteStats(S).each_center_max(9), 0)    # 间隙中心


class TestErrors(unittest.TestCase):
    def test_non_string_text(self):
        with self.assertRaises(Erro):
            BruteStats(123)

    def test_span_out_of_range(self):
        p = BruteStats("ab")
        for lo, hi in [(0, 3), (-1, 1), (1, 0)]:
            with self.assertRaises(Erro):
                p.is_palindrome(lo, hi)

    def test_center_out_of_range(self):
        p = BruteStats("ab")
        with self.assertRaises(Erro):
            p.each_center_max(-1)
        with self.assertRaises(Erro):
            p.each_center_max(2 * len(p) + 1)

    def test_occurrence_bad_pattern(self):
        p = BruteStats("abcab")
        with self.assertRaises(Erro):
            p.occurrence_count("")        # 空串
        with self.assertRaises(Erro):
            p.occurrence_count("ab")      # 不是回文
        with self.assertRaises(Erro):
            p.occurrence_count(12)        # 非字符串


if __name__ == "__main__":
    unittest.main()
