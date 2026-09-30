"""mobius 现有逐数枚举行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from mobius.mobius import Erro, Inversion, NumberRangeError, ValueTypeError


def build_inv(upper=60):
    return Inversion(upper)


class TestConstruction(unittest.TestCase):
    def test_upper_kept(self):
        self.assertEqual(Inversion(97).upper(), 97)

    def test_zero_upper_allowed(self):
        self.assertEqual(Inversion(0).upper(), 0)

    def test_negative_upper_rejected(self):
        with self.assertRaises(NumberRangeError):
            Inversion(-1)

    def test_bool_upper_rejected(self):
        with self.assertRaises(ValueTypeError):
            Inversion(True)

    def test_non_int_upper_rejected(self):
        with self.assertRaises(ValueTypeError):
            Inversion(2.5)

    def test_range_error_is_erro(self):
        self.assertTrue(issubclass(NumberRangeError, Erro))

    def test_type_error_is_erro(self):
        self.assertTrue(issubclass(ValueTypeError, Erro))


class TestMobius(unittest.TestCase):
    def test_mobius_one(self):
        self.assertEqual(Inversion(10).mobius(1), 1)

    def test_mobius_prime(self):
        self.assertEqual(Inversion(10).mobius(7), -1)

    def test_mobius_two_primes(self):
        self.assertEqual(Inversion(10).mobius(6), 1)

    def test_mobius_square_factor(self):
        self.assertEqual(Inversion(10).mobius(12), 0)
        self.assertEqual(Inversion(10).mobius(49), 0)

    def test_mobius_values_ascending(self):
        self.assertEqual(Inversion(10).mobius_values(),
                         (1, -1, -1, 0, -1, 1, -1, 0, 0, 1))

    def test_mobius_zero_upper(self):
        self.assertEqual(Inversion(0).mobius_values(), ())

    def test_mobius_zero_rejected(self):
        with self.assertRaises(NumberRangeError):
            Inversion(10).mobius(0)

    def test_mobius_negative_rejected(self):
        with self.assertRaises(NumberRangeError):
            Inversion(10).mobius(-3)

    def test_mobius_non_int_rejected(self):
        with self.assertRaises(ValueTypeError):
            Inversion(10).mobius(None)


class TestPairs(unittest.TestCase):
    def test_gcd_basic(self):
        self.assertEqual(Inversion(10).gcd(12, 18), 6)
        self.assertEqual(Inversion(10).gcd(7, 13), 1)

    def test_gcd_negative_rejected(self):
        with self.assertRaises(NumberRangeError):
            Inversion(10).gcd(-1, 5)

    def test_count_coprime_pairs_small(self):
        self.assertEqual(Inversion(10).count_coprime_pairs(1), 0)
        self.assertEqual(Inversion(10).count_coprime_pairs(3), 3)

    def test_count_coprime_pairs_zero_limit(self):
        self.assertEqual(Inversion(10).count_coprime_pairs(0), 0)

    def test_count_pairs_gcd_one(self):
        self.assertEqual(Inversion(10).count_pairs_gcd(3, 1), 7)

    def test_count_pairs_gcd_same(self):
        self.assertEqual(Inversion(10).count_pairs_gcd(3, 3), 1)

    def test_count_pairs_gcd_zero_rejected(self):
        with self.assertRaises(NumberRangeError):
            Inversion(10).count_pairs_gcd(10, 0)

    def test_count_coprime_pairs_in(self):
        self.assertEqual(
            Inversion(10).count_coprime_pairs_in([2, 3, 4, 5, 6]), 6)

    def test_count_coprime_pairs_in_bad_value(self):
        with self.assertRaises(NumberRangeError):
            Inversion(10).count_coprime_pairs_in([2, 0])

    def test_count_coprime_pairs_in_non_sequence(self):
        with self.assertRaises(ValueTypeError):
            Inversion(10).count_coprime_pairs_in(7)


class TestDeterminism(unittest.TestCase):
    def test_repeated_mobius_same(self):
        s = build_inv(80)
        first = s.mobius_values()
        for _ in range(3):
            self.assertEqual(s.mobius_values(), first)

    def test_repeated_count_same(self):
        s = build_inv()
        first = s.count_coprime_pairs(30)
        for _ in range(3):
            self.assertEqual(s.count_coprime_pairs(30), first)

    def test_counters_reset_and_grow(self):
        s = build_inv()
        s.reset_counts()
        self.assertEqual(s.trial_divisions(), 0)
        s.mobius_values()
        after = s.trial_divisions()
        self.assertGreater(after, 0)
        s.reset_counts()
        self.assertEqual(s.trial_divisions(), 0)
        s.mobius_values()
        self.assertEqual(s.trial_divisions(), after)

    def test_two_instances_do_not_share_state(self):
        a = build_inv()
        b = build_inv()
        a.mobius_values()
        self.assertEqual(b.trial_divisions(), 0)


if __name__ == "__main__":
    unittest.main()
