"""NaiveStr 现有行为的锁定测试。"""

import unittest

from strhash import HashError, HashIndexError, NaiveStr


class TestConstruction(unittest.TestCase):
    def test_text_and_len(self):
        t = NaiveStr("banana")
        self.assertEqual(t.text, "banana")
        self.assertEqual(len(t), 6)

    def test_repr(self):
        self.assertEqual(repr(NaiveStr("abc")), "<NaiveStr 3 chars>")

    def test_empty_text_is_allowed(self):
        t = NaiveStr("")
        self.assertEqual(len(t), 0)
        self.assertEqual(t.text, "")

    def test_non_string_raises_type_error(self):
        with self.assertRaises(TypeError):
            NaiveStr(None)
        with self.assertRaises(TypeError):
            NaiveStr(123)

    def test_errors_share_one_root(self):
        self.assertTrue(issubclass(HashIndexError, HashError))


class TestSubstrAndRange(unittest.TestCase):
    def test_substr_slice(self):
        t = NaiveStr("banana")
        self.assertEqual(t.substr(1, 4), "ana")
        self.assertEqual(t.substr(0, 0), "")

    def test_range_type_and_bounds(self):
        t = NaiveStr("abc")
        with self.assertRaises(HashIndexError):
            t.substr("0", 1)
        with self.assertRaises(HashIndexError):
            t.substr(0, 4)
        with self.assertRaises(HashIndexError):
            t.substr(2, 1)

    def test_bool_is_not_an_index(self):
        t = NaiveStr("abc")
        with self.assertRaises(HashIndexError):
            t.substr(True, 2)


class TestIsEqual(unittest.TestCase):
    def test_same_content_different_position(self):
        t = NaiveStr("banana")
        self.assertTrue(t.is_equal(1, 4, 3, 6))

    def test_different_content(self):
        t = NaiveStr("banana")
        self.assertFalse(t.is_equal(0, 3, 3, 6))

    def test_empty_ranges_are_equal(self):
        t = NaiveStr("banana")
        self.assertTrue(t.is_equal(0, 0, 6, 6))

    def test_out_of_bounds_raises(self):
        t = NaiveStr("abc")
        with self.assertRaises(HashIndexError):
            t.is_equal(0, 5, 0, 1)


class TestLcp(unittest.TestCase):
    def test_prefix_of_two_positions(self):
        t = NaiveStr("banana")
        self.assertEqual(t.lcp(1, 3), 3)

    def test_same_index_is_whole_suffix(self):
        t = NaiveStr("banana")
        self.assertEqual(t.lcp(2, 2), 4)

    def test_last_indexes(self):
        t = NaiveStr("abc")
        self.assertEqual(t.lcp(2, 2), 1)

    def test_index_out_of_bounds(self):
        t = NaiveStr("abc")
        with self.assertRaises(HashIndexError):
            t.lcp(0, 3)


class TestContainsAndCount(unittest.TestCase):
    def test_contains_overlapping_pattern(self):
        t = NaiveStr("aaaa")
        self.assertTrue(t.contains("aa"))

    def test_contains_missing(self):
        t = NaiveStr("banana")
        self.assertFalse(t.contains("zz"))

    def test_contains_empty_pattern(self):
        self.assertTrue(NaiveStr("").contains(""))

    def test_contains_pattern_longer_than_text(self):
        self.assertFalse(NaiveStr("ab").contains("abc"))

    def test_count_pattern_overlapping(self):
        t = NaiveStr("banana")
        self.assertEqual(t.count_pattern("ana"), 2)

    def test_count_pattern_all_same(self):
        t = NaiveStr("aaaa")
        self.assertEqual(t.count_pattern("aa"), 3)

    def test_count_pattern_empty(self):
        self.assertEqual(NaiveStr("abc").count_pattern(""), 4)

    def test_count_pattern_longer_than_text(self):
        self.assertEqual(NaiveStr("ab").count_pattern("abc"), 0)

    def test_count_pattern_type(self):
        with self.assertRaises(TypeError):
            NaiveStr("abc").count_pattern(1)


class TestDistinctAndRotation(unittest.TestCase):
    def test_distinct_of_banana(self):
        self.assertEqual(NaiveStr("banana").count_distinct_substrings(), 15)

    def test_distinct_of_single(self):
        self.assertEqual(NaiveStr("a").count_distinct_substrings(), 1)

    def test_distinct_of_empty(self):
        self.assertEqual(NaiveStr("").count_distinct_substrings(), 0)

    def test_distinct_of_all_same(self):
        self.assertEqual(NaiveStr("aaaa").count_distinct_substrings(), 4)

    def test_rotation_true(self):
        self.assertTrue(NaiveStr("abcde").is_rotation("cdeab"))

    def test_rotation_false_on_different_content(self):
        self.assertFalse(NaiveStr("abcde").is_rotation("cdeaa"))

    def test_rotation_different_length(self):
        self.assertFalse(NaiveStr("abc").is_rotation("ab"))

    def test_rotation_of_empty(self):
        self.assertTrue(NaiveStr("").is_rotation(""))


class TestCompareCount(unittest.TestCase):
    def test_counts_until_first_mismatch(self):
        t = NaiveStr("banana")
        self.assertEqual(t.compare_count(0, 3, 3, 6), 1)

    def test_counts_whole_equal_slice(self):
        t = NaiveStr("banana")
        self.assertEqual(t.compare_count(1, 4, 3, 6), 3)

    def test_zero_when_a_range_is_empty(self):
        t = NaiveStr("banana")
        self.assertEqual(t.compare_count(0, 0, 1, 4), 0)


class TestDeterminism(unittest.TestCase):
    def test_repeated_calls_agree(self):
        t = NaiveStr("banana")
        first = (
            t.is_equal(1, 4, 3, 6),
            t.lcp(1, 3),
            t.count_pattern("ana"),
            t.count_distinct_substrings(),
            t.is_rotation("anaban"),
            t.compare_count(1, 4, 3, 6),
        )
        second = (
            t.is_equal(1, 4, 3, 6),
            t.lcp(1, 3),
            t.count_pattern("ana"),
            t.count_distinct_substrings(),
            t.is_rotation("anaban"),
            t.compare_count(1, 4, 3, 6),
        )
        self.assertEqual(first, second)

    def test_two_instances_do_not_share_state(self):
        a = NaiveStr("banana")
        b = NaiveStr("aaaa")
        self.assertEqual(a.count_distinct_substrings(), 15)
        self.assertEqual(b.count_distinct_substrings(), 4)
        self.assertEqual(a.count_distinct_substrings(), 15)


if __name__ == "__main__":
    unittest.main()
