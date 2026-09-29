"""基线测试：锁住改造前 NaiveMat 与各模块函数的现状行为。

这些用例描述的是当前"朴素循环"实现对外可见的事实——乘法是三重循环、
幂是连续自乘、斐波那契是逐个递推——改造后必须继续成立，因此本文件
一字不得修改。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from matx.mat import (
    IndexError,
    InvalidModuloError,
    MatError,
    NaiveMat,
    ShapeError,
    fib,
    mat_add,
    mat_diagonal,
    mat_identity,
    mat_mul,
    mat_power,
    mat_zeros,
)


class TestConstructors(unittest.TestCase):
    def test_zeros(self):
        self.assertEqual(mat_zeros(1), [[0]])
        self.assertEqual(mat_zeros(3), [[0, 0, 0], [0, 0, 0], [0, 0, 0]])

    def test_identity(self):
        self.assertEqual(mat_identity(2), [[1, 0], [0, 1]])
        self.assertEqual(mat_identity(1), [[1]])

    def test_diagonal(self):
        self.assertEqual(mat_diagonal([2, 3, 4]), [[2, 0, 0], [0, 3, 0], [0, 0, 4]])
        self.assertEqual(mat_diagonal([]), [])


class TestMatMul(unittest.TestCase):
    def test_identity_is_neutral(self):
        a = [[1, 2], [3, 4]]
        self.assertEqual(mat_mul(a, mat_identity(2)), a)
        self.assertEqual(mat_mul(mat_identity(2), a), a)

    def test_known_product(self):
        a = [[1, 2], [3, 4]]
        b = [[5, 6], [7, 8]]
        self.assertEqual(mat_mul(a, b), [[19, 22], [43, 50]])

    def test_one_by_one(self):
        self.assertEqual(mat_mul([[7]], [[6]]), [[42]])

    def test_with_modulo(self):
        a = [[1, 2], [3, 4]]
        b = [[5, 6], [7, 8]]
        self.assertEqual(mat_mul(a, b, mod=7), [[5, 1], [1, 1]])

    def test_inner_dimension_mismatch_raises(self):
        with self.assertRaises(ShapeError):
            mat_mul([[1, 2, 3]], [[1, 2]])

    def test_zero_modulo_raises(self):
        with self.assertRaises(InvalidModuloError):
            mat_mul([[1]], [[1]], mod=0)


class TestMatAdd(unittest.TestCase):
    def test_add(self):
        self.assertEqual(mat_add([[1, 2], [3, 4]], [[10, 20], [30, 40]]),
                         [[11, 22], [33, 44]])

    def test_dimension_mismatch_raises(self):
        with self.assertRaises(ShapeError):
            mat_add([[1, 2]], [[1], [2]])


class TestMatPower(unittest.TestCase):
    def test_zero_power_is_identity(self):
        a = [[2, 0], [0, 3]]
        self.assertEqual(mat_power(a, 0), mat_identity(2))

    def test_one_power_is_self(self):
        a = [[1, 2], [3, 4]]
        self.assertEqual(mat_power(a, 1), a)

    def test_small_powers(self):
        a = [[1, 1], [1, 0]]
        self.assertEqual(mat_power(a, 2), [[2, 1], [1, 1]])
        self.assertEqual(mat_power(a, 3), [[3, 2], [2, 1]])
        self.assertEqual(mat_power(a, 5), [[8, 5], [5, 3]])

    def test_power_with_modulo(self):
        a = [[1, 1], [1, 0]]
        self.assertEqual(mat_power(a, 5, mod=7), [[1, 5], [5, 3]])
        self.assertEqual(mat_power(a, 10, mod=7), [[5, 6], [6, 6]])

    def test_negative_power_raises(self):
        with self.assertRaises(IndexError):
            mat_power([[1]], -1)

    def test_zero_modulo_raises(self):
        with self.assertRaises(InvalidModuloError):
            mat_power([[1]], 3, mod=0)


class TestFib(unittest.TestCase):
    def test_head_values(self):
        self.assertEqual([fib(i) for i in range(11)],
                         [0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55])

    def test_with_modulo(self):
        self.assertEqual(fib(10, mod=7), 55 % 7)
        self.assertEqual(fib(0, mod=7), 0)
        self.assertEqual(fib(1, mod=7), 1)

    def test_negative_raises(self):
        with self.assertRaises(IndexError):
            fib(-3)


class TestNaiveMat(unittest.TestCase):
    def test_mul_method(self):
        a = NaiveMat([[1, 2], [3, 4]])
        b = NaiveMat([[5, 6], [7, 8]])
        self.assertEqual(a.mul(b).to_list(), [[19, 22], [43, 50]])

    def test_power_method(self):
        a = NaiveMat([[1, 1], [1, 0]])
        self.assertEqual(a.power(5).to_list(), [[8, 5], [5, 3]])

    def test_add_method(self):
        a = NaiveMat([[1, 1], [1, 0]])
        self.assertEqual(a.add(a).to_list(), [[2, 2], [2, 0]])

    def test_identity_method(self):
        a = NaiveMat([[1, 2], [3, 4]])
        self.assertEqual(a.identity().to_list(), [[1, 0], [0, 1]])

    def test_non_square_raises(self):
        with self.assertRaises(ShapeError):
            NaiveMat([[1, 2, 3], [4, 5, 6]])

    def test_equality(self):
        self.assertEqual(NaiveMat([[1, 0], [0, 1]]), NaiveMat([[1, 0], [0, 1]]))


class TestErrorsAndDeterminism(unittest.TestCase):
    def test_errors_share_base_class(self):
        self.assertTrue(issubclass(ShapeError, MatError))
        self.assertTrue(issubclass(IndexError, MatError))
        self.assertTrue(issubclass(InvalidModuloError, MatError))

    def test_fixed_input_repeatable(self):
        def run():
            a = [[1, 1], [1, 0]]
            return mat_power(a, 12), mat_mul(a, a), fib(20)

        self.assertEqual(run(), run())


if __name__ == "__main__":
    unittest.main()
