"""基线测试：锁住改造前 intervaldp.interval.IntervalKit 的现状行为。

这些断言描述的是当前朴素实现的事实，不是最终应当的样子：

  - merge_cost 对每个区间枚举全部分裂点，把左右两半的最优代价相加再叠加
    本区间的石子重量，取最小；
  - best_split 用同样的枚举找出把整段切成两段的最优分裂点；
  - longest_valid 对每个子串从头用栈逐字符重新扫描，判定其是否合法；
  - min_add 对每个子串从头扫描数出未匹配的左右括号数并取最小。

改造时本文件一字不得修改，且必须保持全绿。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intervaldp.interval import (  # noqa: E402
    IntervalKit,
    IntervalErro,
    TextErro,
    StoneErro,
    CostErro,
)


class TestMergeCostBaseline(unittest.TestCase):
    def setUp(self):
        self.k = IntervalKit()

    def test_single_stone_is_zero(self):
        self.assertEqual(self.k.merge_cost([5]), 0)

    def test_two_stones(self):
        self.assertEqual(self.k.merge_cost([2, 3]), 5)

    def test_classic_three_stones(self):
        self.assertEqual(self.k.merge_cost([1, 2, 3]), 9)

    def test_classic_four_stones(self):
        self.assertEqual(self.k.merge_cost([4, 1, 1, 4]), 18)

    def test_all_equal(self):
        self.assertEqual(self.k.merge_cost([3, 3, 3]), 15)

    def test_unit_cost_scales(self):
        self.assertEqual(self.k.merge_cost([3, 3, 3], 2), 30)

    def test_zero_stones_give_zero_cost(self):
        self.assertEqual(self.k.merge_cost([0, 0, 0]), 0)

    def test_sub_range(self):
        self.assertEqual(self.k.merge_cost([4, 1, 1, 4], 1, 0, 2), 5)
        self.assertEqual(self.k.merge_cost([4, 1, 1, 4], 1, 1, 3), 2)

    def test_split_visits_positive(self):
        self.k.merge_cost([4, 1, 1, 4])
        self.assertGreater(self.k.split_visits, 0)

    def test_empty_stones_raise(self):
        with self.assertRaises(StoneErro):
            self.k.merge_cost([])

    def test_negative_stone_raises(self):
        with self.assertRaises(StoneErro):
            self.k.merge_cost([1, -1, 2])

    def test_float_stone_raises(self):
        with self.assertRaises(StoneErro):
            self.k.merge_cost([1, 2.5])

    def test_bool_is_not_int(self):
        with self.assertRaises(StoneErro):
            self.k.merge_cost([1, True])

    def test_bad_cost_raises(self):
        with self.assertRaises(CostErro):
            self.k.merge_cost([1, 2], -1)

    def test_range_out_of_bounds_raises(self):
        with self.assertRaises(StoneErro):
            self.k.merge_cost([1, 2, 3], 1, 0, 9)


class TestBestSplitBaseline(unittest.TestCase):
    def setUp(self):
        self.k = IntervalKit()

    def test_three_stones_split(self):
        self.assertEqual(self.k.best_split([1, 2, 3]), 2)

    def test_four_stones_split(self):
        self.assertEqual(self.k.best_split([4, 1, 1, 4]), 1)

    def test_two_stones_split(self):
        self.assertEqual(self.k.best_split([1, 2]), 1)

    def test_split_returns_int(self):
        self.assertIsInstance(self.k.best_split([1, 2, 3]), int)

    def test_single_stone_raises(self):
        with self.assertRaises(StoneErro):
            self.k.best_split([7])

    def test_empty_raises(self):
        with self.assertRaises(StoneErro):
            self.k.best_split([])

    def test_bad_cost_raises(self):
        with self.assertRaises(CostErro):
            self.k.best_split([1, 2, 3], 1.5)


class TestLongestValidBaseline(unittest.TestCase):
    def setUp(self):
        self.k = IntervalKit()

    def test_empty_is_zero(self):
        self.assertEqual(self.k.longest_valid(""), 0)

    def test_single_open_is_zero(self):
        self.assertEqual(self.k.longest_valid("("), 0)

    def test_simple_pair(self):
        self.assertEqual(self.k.longest_valid("()"), 2)

    def test_nested(self):
        self.assertEqual(self.k.longest_valid("((()))"), 6)

    def test_all_three_kinds(self):
        self.assertEqual(self.k.longest_valid("()[]{}"), 6)

    def test_no_valid_brackets(self):
        self.assertEqual(self.k.longest_valid("((("), 0)

    def test_interleaved_is_invalid(self):
        self.assertEqual(self.k.longest_valid("([)]"), 0)

    def test_classic_run(self):
        self.assertEqual(self.k.longest_valid(")()())"), 4)

    def test_concatenated_runs(self):
        self.assertEqual(self.k.longest_valid("()(())"), 6)

    def test_char_visits_positive(self):
        self.k.longest_valid("()[]")
        self.assertGreater(self.k.char_visits, 0)

    def test_non_string_raises(self):
        with self.assertRaises(TextErro):
            self.k.longest_valid(123)

    def test_illegal_char_raises(self):
        with self.assertRaises(TextErro):
            self.k.longest_valid("(a)")


class TestMinAddBaseline(unittest.TestCase):
    def setUp(self):
        self.k = IntervalKit()

    def test_empty_is_zero(self):
        self.assertEqual(self.k.min_add(""), 0)

    def test_already_valid_is_zero(self):
        self.assertEqual(self.k.min_add("()[]{}"), 0)
        self.assertEqual(self.k.min_add("((()))"), 0)

    def test_only_openers(self):
        self.assertEqual(self.k.min_add("((("), 3)

    def test_only_closers(self):
        self.assertEqual(self.k.min_add(")))"), 3)

    def test_reversed_pair(self):
        self.assertEqual(self.k.min_add(")("), 2)

    def test_interleaved(self):
        self.assertEqual(self.k.min_add("([)]"), 2)

    def test_trailing_opener(self):
        self.assertEqual(self.k.min_add("()("), 1)

    def test_mixed_run(self):
        self.assertEqual(self.k.min_add(")()("), 2)

    def test_illegal_char_raises(self):
        with self.assertRaises(TextErro):
            self.k.min_add("()*")


class TestDeterminismBaseline(unittest.TestCase):
    def test_repeated_calls_agree(self):
        stones = [3, 1, 4, 1, 5]
        text = "()(()))((("
        k1 = IntervalKit()
        k2 = IntervalKit()
        self.assertEqual(k1.merge_cost(stones), k2.merge_cost(stones))
        self.assertEqual(k1.best_split(stones), k2.best_split(stones))
        self.assertEqual(k1.longest_valid(text), k2.longest_valid(text))
        self.assertEqual(k1.min_add(text), k2.min_add(text))

    def test_counts_reset_between_calls(self):
        k = IntervalKit()
        stones = [4, 1, 1, 4]
        k.merge_cost(stones)
        first = k.split_visits
        k.merge_cost(stones)
        self.assertEqual(k.split_visits, first)
        text = "()(())"
        k.longest_valid(text)
        first_chars = k.char_visits
        k.longest_valid(text)
        self.assertEqual(k.char_visits, first_chars)

    def test_fresh_instance_has_zero_counts(self):
        k = IntervalKit()
        self.assertEqual(k.split_visits, 0)
        self.assertEqual(k.char_visits, 0)

    def test_erro_hierarchy(self):
        self.assertTrue(issubclass(TextErro, IntervalErro))
        self.assertTrue(issubclass(StoneErro, IntervalErro))
        self.assertTrue(issubclass(CostErro, IntervalErro))
        self.assertTrue(issubclass(IntervalErro, Exception))


if __name__ == "__main__":
    unittest.main()
