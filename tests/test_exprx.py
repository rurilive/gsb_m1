"""exprx 回归测试：覆盖四个线上缺陷及基础语义。

运行方式（仓库根目录）：
    python3 -m unittest discover -s tests -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from exprx import Evaluator, evaluate


class TestUnaryMinusPrecedence(unittest.TestCase):
    """缺陷 1：-2^2 应得 -4，一元负号优先级必须低于乘方。"""

    def test_negative_power(self):
        self.assertEqual(evaluate("-2^2"), -4)

    def test_parenthesized_negative_base(self):
        self.assertEqual(evaluate("(-2)^2"), 4)

    def test_negative_exponent(self):
        self.assertEqual(evaluate("2^-3"), 0.125)

    def test_power_right_associative(self):
        self.assertEqual(evaluate("2^3^2"), 512)

    def test_double_negation(self):
        self.assertEqual(evaluate("--3"), 3)

    def test_negation_in_product(self):
        self.assertEqual(evaluate("-2 * -3"), 6)

    def test_negation_binds_tighter_than_add(self):
        self.assertEqual(evaluate("1 + -2"), -1)


class TestShortCircuit(unittest.TestCase):
    """缺陷 2：and/or 必须短路，左侧定值后右侧不求值。"""

    def test_and_short_circuits_division_by_zero(self):
        self.assertIs(evaluate("x != 0 and 10 / x > 2", {"x": 0}), False)

    def test_or_short_circuits_division_by_zero(self):
        self.assertIs(evaluate("x == 0 or 10 / x > 2", {"x": 0}), True)

    def test_and_evaluates_right_when_left_true(self):
        self.assertIs(evaluate("x != 0 and 10 / x > 2", {"x": 1}), True)

    def test_or_evaluates_right_when_left_false(self):
        self.assertIs(evaluate("x == 0 or 10 / x > 2", {"x": 1}), True)

    def test_and_skips_unbound_name(self):
        self.assertIs(evaluate("1 > 2 and missing > 0"), False)

    def test_or_skips_unbound_name(self):
        self.assertIs(evaluate("1 < 2 or missing > 0"), True)

    def test_result_is_boolean(self):
        self.assertIs(evaluate("1 and 2"), True)
        self.assertIs(evaluate("0 or 0"), False)


class TestFloorDivAndMod(unittest.TestCase):
    """缺陷 3：// 与 % 是向下取整语义，与 Python 一致。"""

    def test_negative_floor_div(self):
        self.assertEqual(evaluate("-7 // 2"), -4)

    def test_negative_mod(self):
        self.assertEqual(evaluate("-7 % 2"), 1)

    def test_positive_operands(self):
        self.assertEqual(evaluate("7 // 2"), 3)
        self.assertEqual(evaluate("7 % 2"), 1)

    def test_negative_divisor(self):
        self.assertEqual(evaluate("7 // -2"), -4)
        self.assertEqual(evaluate("7 % -2"), -1)

    def test_both_negative(self):
        self.assertEqual(evaluate("-7 // -2"), 3)
        self.assertEqual(evaluate("-7 % -2"), -1)

    def test_mod_identity(self):
        # a == (a // b) * b + a % b 对负数同样成立
        self.assertEqual(evaluate("(a // b) * b + a % b", {"a": -7, "b": 2}), -7)

    def test_float_operands(self):
        self.assertEqual(evaluate("-7.5 % 2"), 0.5)
        self.assertEqual(evaluate("-7.5 // 2"), -4.0)


class TestLetScoping(unittest.TestCase):
    """缺陷 4：let 绑定只在 body 内可见，不污染外层及后续求值。"""

    def test_let_basic(self):
        self.assertEqual(evaluate("let x = 99 in x + 1"), 100)

    def test_let_does_not_leak_between_evaluations(self):
        ev = Evaluator()
        ev.evaluate("let x = 99 in x")
        with self.assertRaises(NameError):
            ev.evaluate("x")

    def test_let_does_not_clobber_external_variable(self):
        ev = Evaluator()
        ev.evaluate("let x = 99 in x", {"x": 1})
        self.assertEqual(ev.evaluate("x"), 1)

    def test_nested_let_shadowing(self):
        self.assertEqual(evaluate("let x = 1 in (let x = 99 in x) + x"), 100)

    def test_let_body_failure_restores_binding(self):
        ev = Evaluator()
        with self.assertRaises(ZeroDivisionError):
            ev.evaluate("let x = 99 in 1 / 0", {"x": 1})
        self.assertEqual(ev.evaluate("x"), 1)

    def test_let_value_sees_outer_binding(self):
        self.assertEqual(evaluate("let x = 2 in let y = x * 3 in y"), 6)


class TestBaselineSemantics(unittest.TestCase):
    """基础语义保持不变。"""

    def test_arithmetic_precedence(self):
        self.assertEqual(evaluate("1 + 2 * 3"), 7)
        self.assertEqual(evaluate("(1 + 2) * 3"), 9)

    def test_comparison(self):
        self.assertIs(evaluate("3 >= 2"), True)
        self.assertIs(evaluate("3 != 3"), False)

    def test_variables_persist_on_instance(self):
        ev = Evaluator()
        ev.evaluate("a + 1", {"a": 1})
        self.assertEqual(ev.evaluate("a * 10"), 10)

    def test_division_by_zero_still_raises(self):
        with self.assertRaises(ZeroDivisionError):
            evaluate("1 / 0")

    def test_unbound_name_still_raises(self):
        with self.assertRaises(NameError):
            evaluate("nope + 1")


if __name__ == "__main__":
    unittest.main()
