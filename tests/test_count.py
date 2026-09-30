"""基线测试：锁住改造前 digitcount.count.IntervalCounter 的现状行为。

这些断言描述的是当前朴素实现的事实，不是最终应当的样子：

  - 四条计数能力都从区间下界逐个枚举到上界，逐数判定条件；
  - find_minimum 同样逐数枚举，返回第一个满足条件的数；
  - independent_enumerate 与 independent_minimum 是两条独立慢速做法；
  - 区间端点、目标数字、数字和与倍数底数都在入口校验。

改造时本文件一字不得修改，且必须保持全绿。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from digitcount.count import (  # noqa: E402
    IntervalCounter,
    Erro,
    RangeErro,
    ValueErro,
    ParamErro,
    MAX_DIGITS,
    DEFAULT_BASE,
)


class TestConstruction(unittest.TestCase):
    def test_default_range(self):
        c = IntervalCounter()
        self.assertEqual((c._low, c._high), (0, 0))

    def test_explicit_range(self):
        c = IntervalCounter(10, 99)
        self.assertEqual((c._low, c._high), (10, 99))

    def test_set_range_returns_self(self):
        c = IntervalCounter()
        self.assertIs(c.set_range(1, 9), c)

    def test_negative_low(self):
        with self.assertRaises(RangeErro):
            IntervalCounter(-1, 5)

    def test_low_greater_than_high(self):
        with self.assertRaises(RangeErro):
            IntervalCounter(9, 1)

    def test_bool_is_not_int(self):
        with self.assertRaises(RangeErro):
            IntervalCounter(True, 5)

    def test_float_endpoint(self):
        with self.assertRaises(RangeErro):
            IntervalCounter(1, 2.5)

    def test_too_many_digits(self):
        with self.assertRaises(RangeErro):
            IntervalCounter(0, 10 ** MAX_DIGITS)

    def test_digits_at_limit_is_ok(self):
        c = IntervalCounter(0, 10 ** MAX_DIGITS - 1)
        self.assertEqual(c.digits, MAX_DIGITS)

    def test_base_constant(self):
        self.assertEqual(DEFAULT_BASE, 10)


class TestWithoutDigit(unittest.TestCase):
    def test_small_range(self):
        c = IntervalCounter(0, 20)
        # 零到二十共二十一个数，只有 7 与 17 含 7。
        self.assertEqual(c.count_without_digit(7), 19)

    def test_zero_digit(self):
        c = IntervalCounter(0, 20)
        self.assertEqual(c.count_without_digit(0), 18)

    def test_single_digit_range(self):
        c = IntervalCounter(5, 9)
        self.assertEqual(c.count_without_digit(3), 5)

    def test_all_digits_present(self):
        c = IntervalCounter(10, 19)
        self.assertEqual(c.count_without_digit(1), 0)

    def test_low_equals_high_present(self):
        c = IntervalCounter(7, 7)
        self.assertEqual(c.count_without_digit(7), 0)

    def test_low_equals_high_absent(self):
        c = IntervalCounter(8, 8)
        self.assertEqual(c.count_without_digit(7), 1)

    def test_target_out_of_range(self):
        c = IntervalCounter(0, 9)
        with self.assertRaises(ValueErro):
            c.count_without_digit(10)

    def test_negative_target(self):
        c = IntervalCounter(0, 9)
        with self.assertRaises(ValueErro):
            c.count_without_digit(-1)


class TestDigitSum(unittest.TestCase):
    def test_zero_sum_only_zero(self):
        c = IntervalCounter(0, 20)
        self.assertEqual(c.count_digit_sum(0), 1)

    def test_sum_ten_small(self):
        c = IntervalCounter(0, 20)
        # 19 的数位和为 10。
        self.assertEqual(c.count_digit_sum(10), 1)

    def test_sum_three_up_to_100(self):
        c = IntervalCounter(0, 100)
        # 3, 12, 21, 30 共 4 个（100 的数位和为 1）。
        self.assertEqual(c.count_digit_sum(3), 4)

    def test_single_digit_range(self):
        c = IntervalCounter(5, 9)
        self.assertEqual(c.count_digit_sum(5), 1)

    def test_low_equals_high(self):
        c = IntervalCounter(28, 28)
        self.assertEqual(c.count_digit_sum(10), 1)

    def test_no_solution(self):
        c = IntervalCounter(0, 9)
        self.assertEqual(c.count_digit_sum(20), 0)

    def test_negative_target(self):
        c = IntervalCounter(0, 9)
        with self.assertRaises(ValueErro):
            c.count_digit_sum(-1)


class TestStrictIncreasing(unittest.TestCase):
    def test_zero_to_nine(self):
        c = IntervalCounter(0, 9)
        # 一位数全部平凡递增，共十个。
        self.assertEqual(c.count_strict_increasing(), 10)

    def test_up_to_hundred(self):
        c = IntervalCounter(0, 100)
        # 12, 13, 14, 15, 16, 17, 18, 19, 23, ... 89, 共 36 个两位数加一位数。
        self.assertEqual(c.count_strict_increasing(), 46)

    def test_no_strict_increasing_two_digit_at_21(self):
        c = IntervalCounter(21, 21)
        self.assertEqual(c.count_strict_increasing(), 0)

    def test_strict_at_12(self):
        c = IntervalCounter(12, 12)
        self.assertEqual(c.count_strict_increasing(), 1)

    def test_equal_adjacent_not_increasing(self):
        c = IntervalCounter(11, 11)
        self.assertEqual(c.count_strict_increasing(), 0)


class TestMultiple(unittest.TestCase):
    def test_multiple_of_one(self):
        c = IntervalCounter(3, 10)
        self.assertEqual(c.count_multiple(1), 8)

    def test_multiple_of_three(self):
        c = IntervalCounter(1, 30)
        self.assertEqual(c.count_multiple(3), 10)

    def test_low_equals_high_multiple(self):
        c = IntervalCounter(9, 9)
        self.assertEqual(c.count_multiple(3), 1)

    def test_zero_multiplier_rejected(self):
        c = IntervalCounter(0, 9)
        with self.assertRaises(ValueErro):
            c.count_multiple(0)

    def test_negative_multiplier(self):
        c = IntervalCounter(0, 9)
        with self.assertRaises(ValueErro):
            c.count_multiple(-3)


class TestFindMinimum(unittest.TestCase):
    def test_without_digit(self):
        c = IntervalCounter(0, 100)
        self.assertEqual(c.find_minimum("without_digit", 7), 0)

    def test_without_digit_skips(self):
        c = IntervalCounter(70, 100)
        self.assertEqual(c.find_minimum("without_digit", 7), 80)

    def test_digit_sum(self):
        c = IntervalCounter(0, 100)
        self.assertEqual(c.find_minimum("digit_sum", 10), 19)

    def test_strict_increasing(self):
        c = IntervalCounter(0, 100)
        self.assertEqual(c.find_minimum("strict_increasing"), 0)

    def test_strict_increasing_two_digit(self):
        c = IntervalCounter(10, 100)
        self.assertEqual(c.find_minimum("strict_increasing"), 12)

    def test_multiple(self):
        c = IntervalCounter(10, 100)
        self.assertEqual(c.find_minimum("multiple", 7), 14)

    def test_no_solution_returns_none(self):
        c = IntervalCounter(10, 20)
        self.assertIsNone(c.find_minimum("digit_sum", 100))

    def test_one_digit_strict(self):
        c = IntervalCounter(5, 5)
        self.assertEqual(c.find_minimum("strict_increasing"), 5)

    def test_bad_condition_name(self):
        c = IntervalCounter(0, 9)
        with self.assertRaises(ParamErro):
            c.find_minimum("bogus")

    def test_non_string_condition(self):
        c = IntervalCounter(0, 9)
        with self.assertRaises(ParamErro):
            c.find_minimum(123)


class TestIndependentPaths(unittest.TestCase):
    def _cases(self):
        return [
            (0, 100),
            (0, 1000),
            (37, 1234),
            (100, 999),
            (0, 9),
            (5, 5),
            (0, 0),
            (500, 1500),
        ]

    def test_without_digit_matches(self):
        for low, high in self._cases():
            c = IntervalCounter()
            dp = c.count_without_digit(7, low, high)
            ind = c.independent_enumerate("without_digit", 7, low, high)
            self.assertEqual(dp, ind, "%d..%d" % (low, high))

    def test_digit_sum_matches(self):
        for low, high in self._cases():
            c = IntervalCounter()
            dp = c.count_digit_sum(9, low, high)
            ind = c.independent_enumerate("digit_sum", 9, low, high)
            self.assertEqual(dp, ind, "%d..%d" % (low, high))

    def test_strict_increasing_matches(self):
        for low, high in self._cases():
            c = IntervalCounter()
            dp = c.count_strict_increasing(low, high)
            ind = c.independent_enumerate("strict_increasing", None, low, high)
            self.assertEqual(dp, ind, "%d..%d" % (low, high))

    def test_multiple_matches(self):
        for low, high in self._cases():
            c = IntervalCounter()
            dp = c.count_multiple(7, low, high)
            ind = c.independent_enumerate("multiple", 7, low, high)
            self.assertEqual(dp, ind, "%d..%d" % (low, high))

    def test_independent_minimum_matches(self):
        pairs = [
            ("without_digit", 7),
            ("digit_sum", 9),
            ("strict_increasing", None),
            ("multiple", 7),
        ]
        for condition, arg in pairs:
            c = IntervalCounter()
            main = c.find_minimum(condition, arg, 20, 500)
            indep = c.independent_minimum(condition, arg, 20, 500)
            self.assertEqual(main, indep, condition)


class TestScaleMetrics(unittest.TestCase):
    def test_enumerate_visits_positive(self):
        c = IntervalCounter(0, 100)
        c.count_without_digit(7)
        self.assertGreater(c.enumerate_visits, 0)

    def test_digit_visits_positive(self):
        c = IntervalCounter(0, 100)
        c.count_digit_sum(9)
        self.assertGreater(c.digit_visits, 0)

    def test_state_visits_zero_baseline(self):
        c = IntervalCounter(0, 100)
        c.count_without_digit(7)
        self.assertEqual(c.state_visits, 0)

    def test_fresh_instance_counts_zero(self):
        c = IntervalCounter(0, 100)
        self.assertEqual(c.enumerate_visits, 0)
        self.assertEqual(c.digit_visits, 0)
        self.assertEqual(c.state_visits, 0)

    def test_width_matches_enumeration(self):
        c = IntervalCounter(10, 20)
        c.count_multiple(3)
        self.assertEqual(c.range_width, 11)
        self.assertEqual(c.enumerate_visits, 11)

    def test_counts_reset_between_calls(self):
        c = IntervalCounter(0, 100)
        c.count_without_digit(7)
        first = c.enumerate_visits
        c.count_without_digit(7)
        self.assertEqual(c.enumerate_visits, first)


class TestDeterminism(unittest.TestCase):
    def test_repeated_calls_agree(self):
        a = IntervalCounter(0, 1000).count_digit_sum(12)
        b = IntervalCounter(0, 1000).count_digit_sum(12)
        self.assertEqual(a, b)

    def test_two_paths_agree_repeatedly(self):
        c = IntervalCounter(0, 1000)
        self.assertEqual(c.count_multiple(9), c.count_multiple(9))

    def test_set_range_then_default(self):
        c = IntervalCounter()
        c.set_range(0, 50)
        self.assertEqual(c.count_multiple(5), 11)

    def test_erro_hierarchy(self):
        self.assertTrue(issubclass(RangeErro, Erro))
        self.assertTrue(issubclass(ValueErro, Erro))
        self.assertTrue(issubclass(ParamErro, Erro))
        self.assertTrue(issubclass(Erro, Exception))


if __name__ == "__main__":
    unittest.main()
