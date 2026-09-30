"""minrot 现有朴素行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from minrot.naive import (
    Erro,
    RotError,
    RotTools,
    is_rotation,
    max_rotation,
    min_rotation,
    min_rotation_index,
    min_shift,
)


class TestMinRotation(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(min_rotation("baba"), "abab")

    def test_index(self):
        self.assertEqual(min_rotation_index("baba"), 1)

    def test_sorted_ascending(self):
        self.assertEqual(min_rotation("abc"), "abc")
        self.assertEqual(min_rotation_index("abc"), 0)

    def test_sorted_descending(self):
        self.assertEqual(min_rotation("cba"), "acb")
        self.assertEqual(min_rotation_index("cba"), 2)

    def test_all_equal(self):
        self.assertEqual(min_rotation("aaaa"), "aaaa")
        self.assertEqual(min_rotation_index("aaaa"), 0)

    def test_repeated_prefix_tie_takes_smallest(self):
        self.assertEqual(min_rotation_index("abab"), 0)

    def test_single_char(self):
        self.assertEqual(min_rotation("a"), "a")

    def test_special_chars(self):
        self.assertEqual(min_rotation("z z"), " zz")

    def test_empty_rejected(self):
        with self.assertRaises(RotError):
            min_rotation("")

    def test_non_str_rejected(self):
        with self.assertRaises(RotError):
            min_rotation(7)


class TestMaxRotation(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(max_rotation("baba"), "baba")

    def test_sorted_descending(self):
        self.assertEqual(max_rotation("cba"), "cba")

    def test_all_equal(self):
        self.assertEqual(max_rotation("aaaa"), "aaaa")

    def test_tie_takes_smallest(self):
        self.assertEqual(max_rotation("abab"), "baba")

    def test_empty_rejected(self):
        with self.assertRaises(RotError):
            max_rotation("")


class TestIsRotation(unittest.TestCase):
    def test_positive(self):
        self.assertTrue(is_rotation("abc", "bca"))

    def test_negative(self):
        self.assertFalse(is_rotation("abc", "acb"))

    def test_unequal_length(self):
        self.assertFalse(is_rotation("ab", "abc"))

    def test_both_empty(self):
        self.assertTrue(is_rotation("", ""))

    def test_single_char(self):
        self.assertTrue(is_rotation("a", "a"))

    def test_non_str_rejected(self):
        with self.assertRaises(RotError):
            is_rotation("ab", 7)


class TestMinShift(unittest.TestCase):
    def test_shift_two(self):
        self.assertEqual(min_shift("abc", "cab"), 2)

    def test_shift_zero(self):
        self.assertEqual(min_shift("abc", "abc"), 0)

    def test_not_rotation(self):
        self.assertEqual(min_shift("abc", "xyz"), -1)

    def test_tie_takes_smallest_shift(self):
        self.assertEqual(min_shift("abab", "abab"), 0)

    def test_empty(self):
        self.assertEqual(min_shift("", ""), 0)

    def test_text_error_is_erro(self):
        self.assertTrue(issubclass(RotError, Erro))


class TestRotTools(unittest.TestCase):
    def test_min_index_matches_plain(self):
        tools = RotTools("baba")
        self.assertEqual(tools.min_rotation_index(), min_rotation_index("baba"))

    def test_min_rotation_matches_plain(self):
        tools = RotTools("baba")
        self.assertEqual(tools.min_rotation(), min_rotation("baba"))

    def test_max_rotation_matches_plain(self):
        tools = RotTools("baba")
        self.assertEqual(tools.max_rotation(), max_rotation("baba"))

    def test_is_rotation_matches_plain(self):
        tools = RotTools("abc")
        self.assertEqual(tools.is_rotation("bca"), is_rotation("abc", "bca"))

    def test_min_shift_matches_plain(self):
        tools = RotTools("abc")
        self.assertEqual(tools.min_shift("cab"), min_shift("abc", "cab"))

    def test_compare_count_grows_and_resets(self):
        tools = RotTools("abcabcabc")
        tools.reset_compare_count()
        self.assertEqual(tools.compare_count(), 0)
        tools.min_rotation_index()
        after = tools.compare_count()
        self.assertGreater(after, 0)
        tools.reset_compare_count()
        self.assertEqual(tools.compare_count(), 0)
        tools.min_rotation_index()
        self.assertEqual(tools.compare_count(), after)

    def test_two_tools_do_not_share_state(self):
        a = RotTools("baba")
        b = RotTools("baba")
        a.min_rotation_index()
        self.assertEqual(b.compare_count(), 0)

    def test_text_accessor(self):
        self.assertEqual(RotTools("hello").text(), "hello")

    def test_non_str_text_rejected(self):
        with self.assertRaises(RotError):
            RotTools(None)


class TestDeterminism(unittest.TestCase):
    def test_repeated_run_same_result(self):
        tools = RotTools("baba")
        first = (
            tools.min_rotation_index(),
            tools.max_rotation_index(),
            tools.min_rotation(),
        )
        for _ in range(3):
            self.assertEqual(
                (
                    tools.min_rotation_index(),
                    tools.max_rotation_index(),
                    tools.min_rotation(),
                ),
                first,
            )


if __name__ == "__main__":
    unittest.main()
