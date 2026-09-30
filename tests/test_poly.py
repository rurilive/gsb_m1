"""Polynomial 现有朴素行为的锁定测试。

这些用例把基线的对外行为钉住：构造与规范、四则运算、朴素卷积、
逐点求值、逐项取模、校验与异常层级。改造时本文件一个字都不许改，
新行为一律另开测试文件。
"""

import unittest

from nttx.poly import (
    EmptyPolynomialError,
    EvaluationError,
    InvalidCoefficientsError,
    InvalidModulusError,
    NttxError,
    Polynomial,
    convolve,
    deduce_length,
    validate_points,
)


class TestConstruction(unittest.TestCase):
    def test_default_is_zero(self):
        p = Polynomial()
        self.assertTrue(p.is_zero())
        self.assertEqual(p.degree(), -1)
        self.assertEqual(p.coefficients, [])

    def test_none_is_zero(self):
        self.assertTrue(Polynomial(None).is_zero())

    def test_trailing_zeros_stripped(self):
        p = Polynomial([1, 2, 0, 0])
        self.assertEqual(p.coefficients, [1, 2])
        self.assertEqual(p.degree(), 1)

    def test_all_zeros_is_zero(self):
        self.assertTrue(Polynomial([0, 0, 0]).is_zero())

    def test_constant(self):
        p = Polynomial([5])
        self.assertEqual(p.degree(), 0)
        self.assertFalse(p.is_zero())

    def test_negative_coefficients_kept(self):
        self.assertEqual(Polynomial([-1, 0, -3]).coefficients, [-1, 0, -3])

    def test_non_integer_raises(self):
        with self.assertRaises(InvalidCoefficientsError):
            Polynomial([1, 2.5])

    def test_bool_is_not_integer(self):
        with self.assertRaises(InvalidCoefficientsError):
            Polynomial([1, True])

    def test_non_iterable_raises(self):
        with self.assertRaises(InvalidCoefficientsError):
            Polynomial(3)

    def test_coefficients_returns_copy(self):
        p = Polynomial([1, 2, 3])
        got = p.coefficients
        got.append(99)
        self.assertEqual(p.coefficients, [1, 2, 3])


class TestEquality(unittest.TestCase):
    def test_equal_ignores_trailing_zeros(self):
        self.assertEqual(Polynomial([1, 2]), Polynomial([1, 2, 0]))

    def test_not_equal_different(self):
        self.assertNotEqual(Polynomial([1, 2]), Polynomial([2, 1]))

    def test_hash_consistent(self):
        self.assertEqual(hash(Polynomial([1, 2])), hash(Polynomial([1, 2, 0])))

    def test_zero_polynomials_equal(self):
        self.assertEqual(Polynomial([]), Polynomial([0, 0]))


class TestAddition(unittest.TestCase):
    def test_same_length(self):
        self.assertEqual(Polynomial([1, 2]) + Polynomial([3, 4]),
                         Polynomial([4, 6]))

    def test_ragged_lengths(self):
        self.assertEqual(Polynomial([1, 2, 3]) + Polynomial([4]),
                         Polynomial([5, 2, 3]))

    def test_with_int(self):
        self.assertEqual(Polynomial([1, 2]) + 5, Polynomial([6, 2]))

    def test_cancels_to_zero(self):
        self.assertTrue((Polynomial([1, 2]) + Polynomial([-1, -2])).is_zero())


class TestSubtraction(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(Polynomial([5, 6]) - Polynomial([1, 2]),
                         Polynomial([4, 4]))

    def test_ragged_lengths(self):
        self.assertEqual(Polynomial([4]) - Polynomial([1, 2, 3]),
                         Polynomial([3, -2, -3]))

    def test_negation(self):
        self.assertEqual(-Polynomial([1, -2, 3]), Polynomial([-1, 2, -3]))


class TestMultiplication(unittest.TestCase):
    def test_basic(self):
        self.assertEqual((Polynomial([1, 2, 3]) * Polynomial([4, 5])),
                         Polynomial([4, 13, 22, 15]))

    def test_self_multiply(self):
        self.assertEqual((Polynomial([1, 1]) * Polynomial([1, 1])),
                         Polynomial([1, 2, 1]))

    def test_zero_times_anything(self):
        self.assertTrue((Polynomial([]) * Polynomial([1, 2, 3])).is_zero())

    def test_constant_times(self):
        self.assertEqual((Polynomial([2]) * Polynomial([3, 4])),
                         Polynomial([6, 8]))

    def test_scalar_coercion(self):
        self.assertEqual(Polynomial([1, 2]) * 3, Polynomial([3, 6]))

    def test_commutative(self):
        a = Polynomial([1, 2, 3, 4])
        b = Polynomial([5, 6])
        self.assertEqual(a * b, b * a)

    def test_modular_wrap_naive(self):
        a = Polynomial([3, 4])
        b = Polynomial([5, 6])
        self.assertEqual(a * b, Polynomial([15, 38, 24]))

    def test_scalar_mul(self):
        self.assertEqual(Polynomial([1, 2]).scalar_mul(4), Polynomial([4, 8]))


class TestConvolveHelpers(unittest.TestCase):
    def test_convolve_basic(self):
        self.assertEqual(convolve([1, 2, 3], [4, 5]), [4, 13, 22, 15])

    def test_convolve_zero(self):
        self.assertEqual(convolve([], [1, 2]), [])

    def test_deduce_length(self):
        self.assertEqual(deduce_length([1, 2, 3], [4, 5]), 4)

    def test_deduce_length_zero(self):
        self.assertEqual(deduce_length([0], [1, 2]), 0)


class TestEvaluation(unittest.TestCase):
    def test_single_point(self):
        self.assertEqual(Polynomial([1, 2, 3]).evaluate(2), 1 + 4 + 12)

    def test_negative_point(self):
        self.assertEqual(Polynomial([1, 2, 3]).evaluate(-1), 1 - 2 + 3)

    def test_zero_polynomial(self):
        self.assertEqual(Polynomial([]).evaluate(7), 0)

    def test_many_points(self):
        self.assertEqual(Polynomial([1, 1]).evaluate_many([0, 1, 2]),
                         [1, 2, 3])

    def test_empty_many_points(self):
        self.assertEqual(Polynomial([1, 2]).evaluate_many([]), [])


class TestScalarMod(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(Polynomial([3, 4, 5]).scalar_mod(3).coefficients,
                         [0, 1, 2])

    def test_negative_normalized(self):
        self.assertEqual(Polynomial([-1, -2]).scalar_mod(5).coefficients,
                         [4, 3])

    def test_zero_result(self):
        self.assertTrue(Polynomial([5, 10]).scalar_mod(5).is_zero())

    def test_modulus_one_raises(self):
        with self.assertRaises(InvalidModulusError):
            Polynomial([1]).scalar_mod(1)

    def test_zero_modulus_raises(self):
        with self.assertRaises(InvalidModulusError):
            Polynomial([1]).scalar_mod(0)

    def test_non_integer_modulus_raises(self):
        with self.assertRaises(InvalidModulusError):
            Polynomial([1]).scalar_mod(7.0)


class TestFromRoots(unittest.TestCase):
    def test_two_roots(self):
        self.assertEqual(Polynomial.from_roots([1, 2]), Polynomial([2, -3, 1]))

    def test_no_roots(self):
        self.assertEqual(Polynomial.from_roots([]), Polynomial([1]))


class TestValidatePoints(unittest.TestCase):
    def test_ok(self):
        self.assertTrue(validate_points(Polynomial([1, 2]), [0, 1]))

    def test_too_few_raises(self):
        with self.assertRaises(EvaluationError):
            validate_points(Polynomial([1, 2, 3]), [0, 1])

    def test_non_polynomial_raises(self):
        with self.assertRaises(EvaluationError):
            validate_points([1, 2], [0, 1])

    def test_zero_polynomial_needs_point(self):
        with self.assertRaises(EmptyPolynomialError):
            validate_points(Polynomial([]), [])


class TestExceptionHierarchy(unittest.TestCase):
    def test_all_inherit_base(self):
        for exc in (InvalidCoefficientsError, InvalidModulusError,
                    EmptyPolynomialError, EvaluationError):
            self.assertTrue(issubclass(exc, NttxError))

    def test_catchable_via_base(self):
        with self.assertRaises(NttxError):
            Polynomial([1, "x"])


class TestDeterminism(unittest.TestCase):
    def test_multiplication_repeatable(self):
        a = Polynomial([1, 2, 3, 4])
        b = Polynomial([5, 6, 7])
        first = (a * b).coefficients
        second = (a * b).coefficients
        self.assertEqual(first, second)

    def test_evaluation_repeatable(self):
        p = Polynomial([3, 1, 4, 1, 5])
        self.assertEqual(p.evaluate(11), p.evaluate(11))


if __name__ == "__main__":
    unittest.main()
