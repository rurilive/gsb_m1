"""NaiveSuffix 现有行为的锁定测试（基线，不许改）。"""

import unittest

from suffixarr import NaiveSuffix, SuffixError, SuffixIndexError


class TestConstruction(unittest.TestCase):
    def test_len_and_text(self):
        t = NaiveSuffix("banana")
        self.assertEqual(len(t), 6)
        self.assertEqual(t.text, "banana")

    def test_repr(self):
        self.assertEqual(repr(NaiveSuffix("abcd")), "<NaiveSuffix 4 chars>")

    def test_empty_text(self):
        t = NaiveSuffix("")
        self.assertEqual(len(t), 0)

    def test_rejects_non_str(self):
        with self.assertRaises(TypeError):
            NaiveSuffix(b"bytes")


class TestSuffixArray(unittest.TestCase):
    def test_banana(self):
        self.assertEqual(NaiveSuffix("banana").suffix_array(), [5, 3, 1, 0, 4, 2])

    def test_empty(self):
        self.assertEqual(NaiveSuffix("").suffix_array(), [])

    def test_single_char(self):
        self.assertEqual(NaiveSuffix("a").suffix_array(), [0])

    def test_all_equal_chars(self):
        self.assertEqual(NaiveSuffix("aaaa").suffix_array(), [3, 2, 1, 0])

    def test_matches_sorted_suffixes(self):
        t = NaiveSuffix("mississippi")
        order = t.suffix_array()
        self.assertEqual(sorted(order), list(range(len(t))))
        texts = [t.text[i:] for i in order]
        self.assertEqual(texts, sorted(texts))


class TestLcpOf(unittest.TestCase):
    def test_same_index(self):
        t = NaiveSuffix("banana")
        self.assertEqual(t.lcp_of(1, 1), 5)

    def test_banana_pair(self):
        t = NaiveSuffix("banana")
        self.assertEqual(t.lcp_of(1, 3), 3)

    def test_no_common_prefix(self):
        t = NaiveSuffix("banana")
        self.assertEqual(t.lcp_of(0, 2), 0)

    def test_empty_text_rejects_any_index(self):
        with self.assertRaises(SuffixIndexError):
            NaiveSuffix("").lcp_of(0, 0)

    def test_out_of_range(self):
        with self.assertRaises(SuffixIndexError):
            NaiveSuffix("abc").lcp_of(0, 3)

    def test_rejects_non_int(self):
        with self.assertRaises(SuffixIndexError):
            NaiveSuffix("abc").lcp_of(0, "1")

    def test_error_is_suffix_error(self):
        with self.assertRaises(SuffixError):
            NaiveSuffix("abc").lcp_of(-1, 0)


class TestCountPattern(unittest.TestCase):
    def test_overlapping(self):
        self.assertEqual(NaiveSuffix("banana").count_pattern("ana"), 2)

    def test_all_equal_char(self):
        self.assertEqual(NaiveSuffix("aaaa").count_pattern("aa"), 3)

    def test_missing(self):
        self.assertEqual(NaiveSuffix("banana").count_pattern("xyz"), 0)

    def test_empty_pattern(self):
        self.assertEqual(NaiveSuffix("abc").count_pattern(""), 4)

    def test_pattern_longer_than_text(self):
        self.assertEqual(NaiveSuffix("ab").count_pattern("abc"), 0)

    def test_rejects_non_str(self):
        with self.assertRaises(TypeError):
            NaiveSuffix("abc").count_pattern(1)


class TestCountDistinctSubstrings(unittest.TestCase):
    def test_banana(self):
        self.assertEqual(NaiveSuffix("banana").count_distinct_substrings(), 15)

    def test_empty(self):
        self.assertEqual(NaiveSuffix("").count_distinct_substrings(), 0)

    def test_single_char(self):
        self.assertEqual(NaiveSuffix("a").count_distinct_substrings(), 1)

    def test_all_equal_chars(self):
        self.assertEqual(NaiveSuffix("aaaa").count_distinct_substrings(), 4)

    def test_abab(self):
        self.assertEqual(NaiveSuffix("abab").count_distinct_substrings(), 7)


class TestLongestRepeatedSubstring(unittest.TestCase):
    def test_banana(self):
        self.assertEqual(NaiveSuffix("banana").longest_repeated_substring(), "ana")

    def test_no_repeat(self):
        self.assertEqual(NaiveSuffix("abcd").longest_repeated_substring(), "")

    def test_all_equal_chars(self):
        self.assertEqual(NaiveSuffix("aaaa").longest_repeated_substring(), "aaa")

    def test_overlapping_repeat(self):
        self.assertEqual(NaiveSuffix("ababab").longest_repeated_substring(), "abab")


class TestCompareCount(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(NaiveSuffix("").compare_count(), 0)

    def test_single_char(self):
        self.assertEqual(NaiveSuffix("a").compare_count(), 0)

    def test_banana_positive(self):
        self.assertGreater(NaiveSuffix("banana").compare_count(), 0)

    def test_all_equal_value(self):
        self.assertEqual(NaiveSuffix("aaaa").compare_count(), 10)

    def test_deterministic(self):
        t = NaiveSuffix("abracadabra")
        self.assertEqual(t.compare_count(), t.compare_count())


if __name__ == "__main__":
    unittest.main()
