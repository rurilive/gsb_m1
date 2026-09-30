"""基线测试：锁住改造前 slidewin.window.WindowStats 的现状行为。

这些断言描述的是当前朴素实现的事实，不是最终应当的样子：

  - sum_bounds 枚举全部子数组，每段从头重新求和，分别得到和不小于目标的最短长度与
    和不大于目标的最长长度；
  - longest_distinct 枚举全部子串，逐个子串从头重新统计不同字符数；
  - distinct_count 走至多相减的口径，至多本身也逐个子串从头重新统计；
  - cover_window 枚举全部子串，逐个从头检查是否覆盖全部目标字符。

改造时本文件一字不得修改，且必须保持全绿。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slidewin.window import (  # noqa: E402
    WindowStats,
    SlideErro,
    SeqErro,
    ParamErro,
)


class TestSumBoundsBaseline(unittest.TestCase):
    def setUp(self):
        self.k = WindowStats()

    def _pair(self, seq, target):
        r = self.k.sum_bounds(seq, target)
        return (r.short_len, r.long_len)

    def test_classic_shortest(self):
        # 目标七时最短是四与三这两项，长度二。
        self.assertEqual(self._pair([2, 3, 1, 2, 4, 3], 7)[0], 2)

    def test_classic_longest(self):
        # 和不大于七的最长段是二加三加一，长度三。
        self.assertEqual(self._pair([2, 3, 1, 2, 4, 3], 7)[1], 3)

    def test_empty_sequence(self):
        self.assertEqual(self._pair([], 5), (0, 0))

    def test_single_element_hits(self):
        self.assertEqual(self._pair([5], 5), (1, 1))

    def test_no_window_meets_min(self):
        # 全部元素为一，目标和为九，凑不满。
        self.assertEqual(self._pair([1, 1, 1], 9)[0], 0)

    def test_no_window_within_max(self):
        # 每个元素都大于目标，没有段的和不大于目标。
        self.assertEqual(self._pair([6, 7, 8], 5)[1], 0)

    def test_zero_target_min_length(self):
        # 目标为零，单个非负元素即可满足不小于零，长度为最小的一。
        self.assertEqual(self._pair([0, 1, 2], 0)[0], 1)

    def test_whole_sequence_is_answer(self):
        self.assertEqual(self._pair([1, 2, 3], 6)[0], 3)
        self.assertEqual(self._pair([1, 2, 3], 6)[1], 3)

    def test_negative_target_and_negatives(self):
        # 目标和为负三，全负序列里最长的一段是整段。
        self.assertEqual(self._pair([-1, -2, -3], -3)[1], 3)

    def test_scan_counts_all_element_visits(self):
        # 三元素序列各段长度之和 3*1+2*2+1*3 = 10。
        self.assertEqual(self.k.sum_bounds([1, 2, 3], 4).scan, 10)

    def test_float_target_raises(self):
        with self.assertRaises(ParamErro):
            self.k.sum_bounds([1, 2], 2.5)

    def test_bool_target_raises(self):
        with self.assertRaises(ParamErro):
            self.k.sum_bounds([1, 2], True)

    def test_float_element_raises(self):
        with self.assertRaises(SeqErro):
            self.k.sum_bounds([1, 2.5], 3)

    def test_non_integer_element_raises(self):
        with self.assertRaises(SeqErro):
            self.k.sum_bounds([1, ""], 3)


class TestLongestDistinctBaseline(unittest.TestCase):
    def setUp(self):
        self.k = WindowStats()

    def _pair(self, text, cap):
        r = self.k.longest_distinct(text, cap)
        return (r.length, r.left)

    def test_classic(self):
        # 至多两个不同字符的最长一段是 bcb，从左端一算起。
        self.assertEqual(self._pair("abcba", 2), (3, 1))

    def test_whole_text_qualifies(self):
        self.assertEqual(self._pair("aabb", 3), (4, 0))

    def test_single_character(self):
        self.assertEqual(self._pair("a", 1), (1, 0))

    def test_empty_text(self):
        self.assertEqual(self._pair("", 2), (0, -1))

    def test_zero_cap_no_window(self):
        # 任何非空子串都至少含一个不同字符，上界为零时无解。
        self.assertEqual(self._pair("abc", 0), (0, -1))

    def test_all_same_character(self):
        self.assertEqual(self._pair("aaaa", 1), (4, 0))

    def test_tie_prefers_leftmost(self):
        # aba 与 bab 都是长度三含两个不同字符，取左端更小的一条。
        self.assertEqual(self._pair("abab", 2), (4, 0))

    def test_scan_counts_all_visits(self):
        # 三字符文本各段长度之和 3*1+2*2+1*3 = 10。
        self.assertEqual(self.k.longest_distinct("abc", 2).scan, 10)

    def test_negative_cap_raises(self):
        with self.assertRaises(ParamErro):
            self.k.longest_distinct("abc", -1)

    def test_bool_cap_raises(self):
        with self.assertRaises(ParamErro):
            self.k.longest_distinct("abc", True)

    def test_non_string_raises(self):
        with self.assertRaises(SeqErro):
            self.k.longest_distinct(123, 2)

    def test_float_cap_raises(self):
        with self.assertRaises(ParamErro):
            self.k.longest_distinct("abc", 2.5)


class TestDistinctCountBaseline(unittest.TestCase):
    def setUp(self):
        self.k = WindowStats()

    def test_classic_cap_two(self):
        # aab 里恰好含两个不同字符的子串是 aab 与 ab，共两个。
        self.assertEqual(self.k.distinct_count("aab", 2), 2)

    def test_exactly_one_distinct(self):
        # aab 里全由同一字符构成的子串是 aa、a、a、b，共四个。
        self.assertEqual(self.k.distinct_count("aab", 1), 4)

    def test_zero_cap_is_zero(self):
        # 非空子串至少含一个不同字符，恰好含零个的个数为零。
        self.assertEqual(self.k.distinct_count("abc", 0), 0)

    def test_empty_text(self):
        self.assertEqual(self.k.distinct_count("", 2), 0)

    def test_single_character(self):
        self.assertEqual(self.k.distinct_count("a", 1), 1)

    def test_cap_exceeds_alphabet(self):
        # 至多含很多个不同字符时，全部子串都被计入之后再相减仍得恰好口径。
        self.assertEqual(self.k.distinct_count("ab", 5), 0)

    def test_repeated_characters(self):
        # aaab 里恰好含两个不同字符的子串是含 b 并把前面的 a 一起带上的那些。
        self.assertEqual(self.k.distinct_count("aaab", 2), 3)

    def test_negative_cap_raises(self):
        with self.assertRaises(ParamErro):
            self.k.distinct_count("abc", -1)

    def test_float_cap_raises(self):
        with self.assertRaises(ParamErro):
            self.k.distinct_count("abc", 1.5)

    def test_non_string_raises(self):
        with self.assertRaises(SeqErro):
            self.k.distinct_count(7, 1)


class TestCoverWindowBaseline(unittest.TestCase):
    def setUp(self):
        self.k = WindowStats()

    def test_classic(self):
        # 目标 b 与 d，最短窗口恰是 bcd，左右端点一与三，长度三。
        self.assertEqual(self.k.cover_window("abcde", "bd"), (1, 3, 3))

    def test_window_at_left(self):
        self.assertEqual(self.k.cover_window("ab", "a"), (0, 0, 1))

    def test_window_at_right(self):
        self.assertEqual(self.k.cover_window("xyz", "z"), (2, 2, 1))

    def test_no_solution(self):
        self.assertEqual(self.k.cover_window("abc", "z"), (-1, -1, 0))

    def test_whole_text_is_answer(self):
        self.assertEqual(self.k.cover_window("ab", "ab"), (0, 1, 2))

    def test_empty_text(self):
        self.assertEqual(self.k.cover_window("", "a"), (-1, -1, 0))

    def test_target_with_repeats_collapses(self):
        # 目标串里重复的字符按集合去重，仍是单个 a。
        self.assertEqual(self.k.cover_window("ba", "aa"), (1, 1, 1))

    def test_cover_window_returns_triple(self):
        r = self.k.cover_window("abcde", "bd")
        self.assertEqual(r, (1, 3, 3))

    def test_scan_counts_all_visits(self):
        # 五字符文本各段长度之和 5*1+4*2+3*3+2*4+1*5 = 35。
        self.k.cover_window("abcde", "ae")
        self.assertEqual(self.k.last_scan, 35)

    def test_empty_target_raises(self):
        with self.assertRaises(ParamErro):
            self.k.cover_window("abc", "")

    def test_non_string_text_raises(self):
        with self.assertRaises(SeqErro):
            self.k.cover_window(5, "a")

    def test_non_iterable_target_raises(self):
        with self.assertRaises(ParamErro):
            self.k.cover_window("abc", 5)


class TestDeterminismBaseline(unittest.TestCase):
    def test_repeated_calls_agree(self):
        seq = [2, 3, 1, 2, 4, 3]
        text = "abcba"
        k1 = WindowStats()
        k2 = WindowStats()
        self.assertEqual(k1.sum_bounds(seq, 7), k2.sum_bounds(seq, 7))
        self.assertEqual(k1.longest_distinct(text, 2), k2.longest_distinct(text, 2))
        self.assertEqual(k1.distinct_count(text, 2), k2.distinct_count(text, 2))
        self.assertEqual(k1.cover_window(text, "ab"), k2.cover_window(text, "ab"))

    def test_scan_resets_between_calls(self):
        k = WindowStats()
        seq = [1, 3, 2, 4]
        k.sum_bounds(seq, 5)
        first = k.last_scan
        k.sum_bounds(seq, 5)
        self.assertEqual(k.last_scan, first)

    def test_fresh_instance_has_zero_scan(self):
        self.assertEqual(WindowStats().last_scan, 0)

    def test_erro_hierarchy(self):
        self.assertTrue(issubclass(SeqErro, SlideErro))
        self.assertTrue(issubclass(ParamErro, SlideErro))
        self.assertTrue(issubclass(SlideErro, Exception))


if __name__ == "__main__":
    unittest.main()
