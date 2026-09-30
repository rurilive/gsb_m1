"""PrefixKit 现有行为的锁定测试（基线，一字不改）。"""

import unittest

from prefixkit.prefix import InvalidInputError, PrefixError, PrefixKit


class TestPrefixFunction(unittest.TestCase):
    def test_simple_pattern(self):
        self.assertEqual(PrefixKit("aabaabaab").prefix_function(), [0, 0, 1, 0, 1, 2, 3, 4, 5, 6])

    def test_all_same(self):
        self.assertEqual(PrefixKit("aaaa").prefix_function(), [0, 0, 1, 2, 3])

    def test_all_distinct(self):
        self.assertEqual(PrefixKit("abcd").prefix_function(), [0, 0, 0, 0, 0])

    def test_single_char(self):
        self.assertEqual(PrefixKit("a").prefix_function(), [0, 0])

    def test_empty_pattern(self):
        self.assertEqual(PrefixKit("").prefix_function(), [0])


class TestPrefixValue(unittest.TestCase):
    def test_value_at_length(self):
        self.assertEqual(PrefixKit("aabaabaab").prefix_value(6), 3)

    def test_value_at_full_length(self):
        self.assertEqual(PrefixKit("aabaabaab").prefix_value(9), 6)

    def test_value_at_zero(self):
        self.assertEqual(PrefixKit("aabaabaab").prefix_value(0), 0)

    def test_value_at_one(self):
        self.assertEqual(PrefixKit("abc").prefix_value(1), 0)


class TestFindOccurrences(unittest.TestCase):
    def test_two_hits(self):
        self.assertEqual(PrefixKit("aabaabaab").find_occurrences("aabaabaabaab"), [0, 3])

    def test_no_hit(self):
        self.assertEqual(PrefixKit("abc").find_occurrences("defdef"), [])

    def test_overlapping_hits(self):
        self.assertEqual(PrefixKit("aa").find_occurrences("aaaa"), [0, 1, 2])

    def test_hit_at_end(self):
        self.assertEqual(PrefixKit("cd").find_occurrences("abcd"), [2])

    def test_single_char_pattern(self):
        self.assertEqual(PrefixKit("a").find_occurrences("banana"), [1, 3, 5])

    def test_text_equal_pattern(self):
        self.assertEqual(PrefixKit("abc").find_occurrences("abc"), [0])

    def test_pattern_longer_than_text(self):
        self.assertEqual(PrefixKit("abcdef").find_occurrences("abc"), [])


class TestCountOccurrences(unittest.TestCase):
    def test_count_two(self):
        self.assertEqual(PrefixKit("aabaabaab").count_occurrences("aabaabaabaab"), 2)

    def test_count_zero(self):
        self.assertEqual(PrefixKit("abc").count_occurrences("defdef"), 0)

    def test_count_overlapping(self):
        self.assertEqual(PrefixKit("aa").count_occurrences("aaaa"), 3)


class TestCountPrefixOccurrences(unittest.TestCase):
    def test_prefix_stats(self):
        stats = PrefixKit("aabaabaab").count_prefix_occurrences()
        self.assertEqual(stats[1], 6)
        self.assertEqual(stats[2], 3)
        self.assertEqual(stats[3], 3)
        self.assertEqual(stats[9], 1)

    def test_all_same(self):
        stats = PrefixKit("aaa").count_prefix_occurrences()
        self.assertEqual(stats[1], 3)
        self.assertEqual(stats[2], 2)
        self.assertEqual(stats[3], 1)

    def test_all_distinct(self):
        stats = PrefixKit("abcd").count_prefix_occurrences()
        self.assertEqual(stats[1], 1)
        self.assertEqual(stats[2], 1)
        self.assertEqual(stats[4], 1)


class TestPeriodInfo(unittest.TestCase):
    def test_periodic(self):
        info = PrefixKit("aabaabaab").period_info()
        self.assertTrue(info["is_periodic"])
        self.assertEqual(info["period"], 3)
        self.assertEqual(info["exponent"], 3)

    def test_all_same(self):
        info = PrefixKit("aaaa").period_info()
        self.assertTrue(info["is_periodic"])
        self.assertEqual(info["period"], 1)
        self.assertEqual(info["exponent"], 4)

    def test_not_periodic(self):
        info = PrefixKit("aabaabaa").period_info()
        self.assertFalse(info["is_periodic"])
        self.assertIsNone(info["period"])

    def test_all_distinct(self):
        info = PrefixKit("abcd").period_info()
        self.assertFalse(info["is_periodic"])

    def test_single_char_not_periodic(self):
        info = PrefixKit("a").period_info()
        self.assertFalse(info["is_periodic"])

    def test_empty_not_periodic(self):
        info = PrefixKit("").period_info()
        self.assertFalse(info["is_periodic"])


class TestMinPeriod(unittest.TestCase):
    def test_periodic(self):
        self.assertEqual(PrefixKit("aabaabaab").min_period(), 3)

    def test_all_same(self):
        self.assertEqual(PrefixKit("aaaa").min_period(), 1)

    def test_not_periodic_returns_length(self):
        self.assertEqual(PrefixKit("aabaabaa").min_period(), 8)

    def test_single_char(self):
        self.assertEqual(PrefixKit("a").min_period(), 1)


class TestSteps(unittest.TestCase):
    def test_prefix_steps_positive(self):
        kit = PrefixKit("aaaa")
        kit.prefix_function()
        self.assertGreater(kit.prefix_steps(), 0)

    def test_search_steps_positive(self):
        kit = PrefixKit("ab")
        kit.find_occurrences("ababab")
        self.assertGreater(kit.search_steps(), 0)

    def test_prefix_steps_repeat(self):
        kit = PrefixKit("aabaabaab")
        kit.prefix_function()
        first = kit.prefix_steps()
        kit.prefix_function()
        self.assertEqual(kit.prefix_steps(), first)


class TestErrors(unittest.TestCase):
    def test_non_string_pattern_rejected(self):
        with self.assertRaises(InvalidInputError):
            PrefixKit(123)

    def test_non_string_text_rejected(self):
        with self.assertRaises(InvalidInputError):
            PrefixKit("abc").find_occurrences(None)

    def test_empty_pattern_search_rejected(self):
        with self.assertRaises(InvalidInputError):
            PrefixKit("").find_occurrences("abc")

    def test_negative_index_rejected(self):
        with self.assertRaises(InvalidInputError):
            PrefixKit("abc").prefix_value(-1)

    def test_index_beyond_length_rejected(self):
        with self.assertRaises(InvalidInputError):
            PrefixKit("abc").prefix_value(4)

    def test_non_integer_index_rejected(self):
        with self.assertRaises(InvalidInputError):
            PrefixKit("abc").prefix_value(1.5)

    def test_bool_index_rejected(self):
        with self.assertRaises(InvalidInputError):
            PrefixKit("abc").prefix_value(True)

    def test_error_base_class(self):
        self.assertTrue(issubclass(InvalidInputError, PrefixError))
        self.assertTrue(issubclass(PrefixError, Exception))


class TestDeterminism(unittest.TestCase):
    def test_prefix_repeat_same(self):
        kit = PrefixKit("aabaabaab")
        self.assertEqual(kit.prefix_function(), kit.prefix_function())

    def test_search_repeat_same(self):
        kit = PrefixKit("aa")
        self.assertEqual(kit.find_occurrences("aaaa"), kit.find_occurrences("aaaa"))

    def test_period_stable(self):
        kit = PrefixKit("aabaabaab")
        self.assertEqual(kit.period_info(), kit.period_info())

    def test_pattern_unchanged(self):
        kit = PrefixKit("aabaabaab")
        kit.prefix_function()
        kit.count_prefix_occurrences()
        kit.period_info()
        self.assertEqual(kit.pattern(), "aabaabaab")


if __name__ == "__main__":
    unittest.main()
