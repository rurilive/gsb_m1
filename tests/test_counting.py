"""Counting 现有朴素行为的锁定测试。

这份基线在改造前后都必须全绿，一个字都不许改动。
"""

import unittest

from inclx.counting import Counting, CountingError


class TestCountingBaseline(unittest.TestCase):
    def setUp(self):
        self.c = Counting()

    def test_count_not_divisible_basic(self):
        self.assertEqual(self.c.count_not_divisible(10, (2, 3)), 3)

    def test_count_not_divisible_empty_primes(self):
        self.assertEqual(self.c.count_not_divisible(5, ()), 5)

    def test_count_not_divisible_zero_limit(self):
        self.assertEqual(self.c.count_not_divisible(0, (2, 3)), 0)

    def test_count_not_divisible_one_limit(self):
        self.assertEqual(self.c.count_not_divisible(1, (2, 3)), 1)

    def test_count_not_divisible_duplicate_primes(self):
        self.assertEqual(self.c.count_not_divisible(10, (2, 2, 3)),
                         self.c.count_not_divisible(10, (2, 3)))

    def test_count_not_divisible_bad_prime_raises(self):
        with self.assertRaises(CountingError):
            self.c.count_not_divisible(10, (2, 4))

    def test_count_not_divisible_bool_prime_rejected(self):
        with self.assertRaises(CountingError):
            self.c.count_not_divisible(10, (True, 3))

    def test_count_coprime_in_range_basic(self):
        self.assertEqual(self.c.count_coprime_in_range(1, 10, (2, 3)), 3)

    def test_count_coprime_in_range_degenerate(self):
        self.assertEqual(self.c.count_coprime_in_range(5, 5, (2,)), 1)
        self.assertEqual(self.c.count_coprime_in_range(5, 5, (5,)), 0)

    def test_count_coprime_in_range_low_above_high(self):
        self.assertEqual(self.c.count_coprime_in_range(9, 3, (2, 3)), 0)

    def test_count_coprime_in_range_coprime_number_one(self):
        self.assertEqual(self.c.count_coprime_in_range(1, 4, (1,)), 4)

    def test_count_union_basic(self):
        self.assertEqual(self.c.count_union([{1, 2, 3}, {3, 4}, {5}]), 5)

    def test_count_union_overlap_not_double_counted(self):
        self.assertEqual(self.c.count_union([{1, 2}, {2, 3}, {1, 3}]), 3)

    def test_count_union_empty(self):
        self.assertEqual(self.c.count_union([]), 0)
        self.assertEqual(self.c.count_union([set(), set()]), 0)

    def test_count_multi_condition_basic(self):
        n = self.c.count_multi_condition(
            30, (lambda v: v % 2 == 0, lambda v: v % 3 == 0))
        self.assertEqual(n, 5)

    def test_count_multi_condition_no_condition(self):
        self.assertEqual(self.c.count_multi_condition(7, ()), 7)

    def test_count_multi_condition_bad_limit(self):
        with self.assertRaises(CountingError):
            self.c.count_multi_condition(-1, ())

    def test_limit_rejects_non_integer(self):
        with self.assertRaises(CountingError):
            self.c.count_not_divisible(1.5, (2,))

    def test_limit_rejects_bool(self):
        with self.assertRaises(CountingError):
            self.c.count_not_divisible(True, (2,))

    def test_negative_prime_raises(self):
        with self.assertRaises(CountingError):
            self.c.count_not_divisible(10, (-2,))

    def test_error_is_value_error(self):
        self.assertTrue(issubclass(CountingError, ValueError))

    def test_deterministic_across_calls(self):
        first = self.c.count_not_divisible(100, (2, 3, 5, 7))
        second = self.c.count_not_divisible(100, (2, 3, 5, 7))
        self.assertEqual(first, second)

    def test_many_values_exact(self):
        self.assertEqual(self.c.count_not_divisible(1000, (2,)), 500)


if __name__ == "__main__":
    unittest.main()
