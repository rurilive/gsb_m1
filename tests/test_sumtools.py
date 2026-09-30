"""数论求和朴素实现的行为基线测试。

这些用例锁住改造前的现状行为：只测现有接口在当下给出的结果，任何改动都不许
让它们变红。
"""

import unittest

from divblock import (
    GcdSumError,
    best_divisor_number_count,
    best_divisor_number_upto,
    coprime_count_upto,
    divisor_count_upto,
    gcd,
    mobius_prefix_upto,
    mobius_sieve,
    naive_pair_count,
    naive_scan_count,
    range_mobius_sum,
    range_totient_sum,
    totient_prefix_upto,
    totient_sieve,
)


class GcdTest(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(gcd(12, 18), 6)
        self.assertEqual(gcd(7, 1), 1)
        self.assertEqual(gcd(5, 5), 5)

    def test_zero_side(self):
        self.assertEqual(gcd(0, 9), 9)
        self.assertEqual(gcd(9, 0), 9)
        self.assertEqual(gcd(0, 0), 0)


class TotientTest(unittest.TestCase):
    def test_sieve_small(self):
        self.assertEqual(totient_sieve(10)[1:], [1, 1, 2, 2, 4, 2, 6, 4, 6, 4])

    def test_prefix(self):
        self.assertEqual(totient_prefix_upto(10), 32)
        self.assertEqual(totient_prefix_upto(0), 0)
        self.assertEqual(totient_prefix_upto(1), 1)

    def test_range(self):
        self.assertEqual(range_totient_sum(5, 10), 26)
        self.assertEqual(range_totient_sum(3, 3), 2)
        self.assertEqual(range_totient_sum(7, 4), 0)
        self.assertEqual(range_totient_sum(0, 0), 0)


class MobiusTest(unittest.TestCase):
    def test_sieve_small(self):
        self.assertEqual(mobius_sieve(10)[1:],
                         [1, -1, -1, 0, -1, 1, -1, 0, 0, 1])

    def test_prefix(self):
        self.assertEqual(mobius_prefix_upto(10), -1)
        self.assertEqual(mobius_prefix_upto(1), 1)
        self.assertEqual(mobius_prefix_upto(0), 0)

    def test_range(self):
        self.assertEqual(range_mobius_sum(4, 6), 0)
        self.assertEqual(range_mobius_sum(6, 4), 0)
        self.assertEqual(range_mobius_sum(2, 2), -1)


class DivisorCountTest(unittest.TestCase):
    def test_small(self):
        self.assertEqual(divisor_count_upto(0), 0)
        self.assertEqual(divisor_count_upto(1), 1)
        self.assertEqual(divisor_count_upto(6), 14)
        self.assertEqual(divisor_count_upto(10), 27)


class CoprimeCountTest(unittest.TestCase):
    def test_small(self):
        self.assertEqual(coprime_count_upto(0, 1), 0)
        self.assertEqual(coprime_count_upto(10, 1), 10)
        self.assertEqual(coprime_count_upto(10, 2), 5)
        self.assertEqual(coprime_count_upto(12, 6), 4)


class BestDivisorNumberTest(unittest.TestCase):
    def test_count(self):
        self.assertEqual(best_divisor_number_count(1), 1)
        self.assertEqual(best_divisor_number_count(10), 4)
        self.assertEqual(best_divisor_number_count(0), 0)

    def test_upto(self):
        self.assertEqual(best_divisor_number_upto(10), 6)
        self.assertEqual(best_divisor_number_upto(1), 1)
        self.assertEqual(best_divisor_number_upto(0), 0)


class ScaleCountTest(unittest.TestCase):
    def test_scan(self):
        self.assertEqual(naive_scan_count(10), 11)
        self.assertEqual(naive_scan_count(0), 1)

    def test_pair(self):
        self.assertEqual(naive_pair_count(10), 121)
        self.assertEqual(naive_pair_count(0), 1)


class ErrorTest(unittest.TestCase):
    def test_negative(self):
        with self.assertRaises(GcdSumError):
            divisor_count_upto(-1)

    def test_bool_rejected(self):
        with self.assertRaises(GcdSumError):
            totient_prefix_upto(True)

    def test_has_position(self):
        try:
            divisor_count_upto(-3)
        except GcdSumError as exc:
            self.assertEqual(exc.position, "n")


if __name__ == "__main__":
    unittest.main()
