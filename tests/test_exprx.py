"""exprx 防回归测试：覆盖一元负号优先级、短路求值、地板除/取模、作用域隔离。

运行方式（仓库根目录）：
    python3 -m unittest discover -s tests
或：
    python3 tests/test_exprx.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from exprx import Evaluator, evaluate  # noqa: E402


class PowerAndNegationTests(unittest.TestCase):
    """现象 1：一元负号必须作用于整个乘方结果。"""

    def test_negative_base_power(self):
        self.assertEqual(evaluate("-2^2"), -4)

    def test_negation_of_parenthesized_power(self):
        self.assertEqual(evaluate("-(2^2)"), -4)

    def test_double_negation(self):
        self.assertEqual(evaluate("--2^2"), 4)

    def test_negative_base_higher_power(self):
        self.assertEqual(evaluate("-2^3"), -8)

    def test_negative_exponent(self):
        self.assertAlmostEqual(evaluate("2^-3"), 0.125)

    def test_negative_base_and_exponent(self):
        self.assertAlmostEqual(evaluate("-2^-2"), -0.25)

    def test_power_right_associative(self):
        self.assertEqual(evaluate("2^3^2"), 512)
        self.assertEqual(evaluate("2^(3^2)"), 512)
        self.assertEqual(evaluate("(2^3)^2"), 64)

    def test_negation_belows_multiplication(self):
        self.assertEqual(evaluate("-2*3"), -6)
        self.assertEqual(evaluate("3*-2"), -6)


class ShortCircuitTests(unittest.TestCase):
    """现象 2：and/or 必须短路，右支不被求值。"""

    def test_and_short_circuits_on_zero_divisor(self):
        self.assertIs(evaluate("x != 0 and 10 / x > 2", {"x": 0}), False)

    def test_or_short_circuits_on_zero_divisor(self):
        self.assertIs(evaluate("x == 0 or 10 / x > 2", {"x": 0}), True)

    def test_and_evaluates_right_when_left_truthy(self):
        self.assertIs(evaluate("x != 0 and 10 / x > 2", {"x": 2}), True)
        self.assertIs(evaluate("x != 0 and 10 / x > 2", {"x": 10}), False)

    def test_or_evaluates_right_when_left_falsy(self):
        self.assertIs(evaluate("x != 0 or 10 / x > 2", {"x": 2}), True)
        self.assertIs(evaluate("x != 0 or x > 0", {"x": 0}), False)

    def test_short_circuit_returns_bool(self):
        self.assertIsInstance(evaluate("1 and 2"), bool)
        self.assertIsInstance(evaluate("0 or 3"), bool)
        self.assertIs(evaluate("0 and 2"), False)
        self.assertIs(evaluate("1 or 2"), True)

    def test_division_by_zero_still_raises_when_reached(self):
        with self.assertRaises(ZeroDivisionError):
            evaluate("10 / 0")
        with self.assertRaises(ZeroDivisionError):
            evaluate("10 // 0")
        with self.assertRaises(ZeroDivisionError):
            evaluate("10 % 0")
        with self.assertRaises(ZeroDivisionError):
            evaluate("x == 0 and 10 / x > 2", {"x": 0})


class FloorDivModuloTests(unittest.TestCase):
    """现象 3：// 与 % 是向下取整语义，余数符号跟随除数。"""

    def test_negative_modulo_positive(self):
        self.assertEqual(evaluate("-7 % 2"), 1)

    def test_positive_modulo_negative(self):
        self.assertEqual(evaluate("7 % -2"), -1)

    def test_negative_modulo_negative(self):
        self.assertEqual(evaluate("-7 % -2"), -1)

    def test_modulo_basic(self):
        self.assertEqual(evaluate("7 % 2"), 1)
        self.assertEqual(evaluate("8 % 2"), 0)

    def test_negative_floor_div_positive(self):
        self.assertEqual(evaluate("-7 // 2"), -4)

    def test_positive_floor_div_negative(self):
        self.assertEqual(evaluate("7 // -2"), -4)

    def test_floor_div_basic(self):
        self.assertEqual(evaluate("7 // 2"), 3)
        self.assertEqual(evaluate("-8 // 2"), -4)

    def test_float_operands_follow_python_semantics(self):
        self.assertAlmostEqual(evaluate("-7.0 % 2"), 1.0)
        self.assertEqual(evaluate("7.5 // 2"), 3.0)

    def test_floor_div_and_modulo_consistency(self):
        # 恒等式：a == (a // b) * b + (a % b)
        for a, b in ((-7, 2), (7, -2), (-7, -2), (9, 4), (-9, 4)):
            q = evaluate(f"{a} // {b}")
            r = evaluate(f"{a} % {b}")
            self.assertEqual(q * b + r, a, f"{a}, {b}")


class ScopeTests(unittest.TestCase):
    """现象 4：let 绑定不逃逸，多次 evaluate 之间互不污染。"""

    def test_nested_let_shadowing(self):
        self.assertEqual(evaluate("let x = 1 in (let x = 99 in x) + x"), 100)

    def test_outer_binding_visible_inside(self):
        self.assertEqual(evaluate("let x = 10 in let y = x + 1 in x + y"), 21)

    def test_inner_binding_not_visible_outside(self):
        with self.assertRaises(NameError):
            evaluate("let x = 99 in x + y")

    def test_let_does_not_leak_between_evaluations(self):
        ev = Evaluator()
        self.assertEqual(ev.evaluate("let x = 99 in x"), 99)
        with self.assertRaises(NameError):
            ev.evaluate("x")

    def test_variables_do_not_leak_between_evaluations(self):
        ev = Evaluator()
        self.assertEqual(ev.evaluate("x + 1", {"x": 1}), 2)
        with self.assertRaises(NameError):
            ev.evaluate("x")

    def test_let_does_not_mutate_caller_variables(self):
        variables = {"x": 1}
        evaluate("let x = 99 in x", variables)
        self.assertEqual(variables, {"x": 1})

    def test_value_evaluated_in_outer_scope(self):
        self.assertEqual(
            evaluate("let x = 1 in let y = (let x = 2 in x) in x + y"), 3
        )

    def test_unbound_variable_raises_name_error(self):
        with self.assertRaises(NameError):
            evaluate("unknown_var + 1")

    def test_scope_restored_after_error(self):
        ev = Evaluator()
        with self.assertRaises(ZeroDivisionError):
            ev.evaluate("let x = 1 in 1 / 0")
        with self.assertRaises(NameError):
            ev.evaluate("x")


class BasicArithmeticTests(unittest.TestCase):
    """常规语义不回退。"""

    def test_arithmetic(self):
        self.assertEqual(evaluate("1 + 2 * 3"), 7)
        self.assertAlmostEqual(evaluate("10 / 4"), 2.5)
        self.assertEqual(evaluate("2 ^ 10"), 1024)

    def test_comparisons(self):
        self.assertIs(evaluate("1 < 2"), True)
        self.assertIs(evaluate("2 <= 2"), True)
        self.assertIs(evaluate("3 == 4"), False)
        self.assertIs(evaluate("3 != 4"), True)

    def test_module_level_convenience_entry_uses_fresh_evaluator(self):
        # 便捷入口每次独立，天然不存在跨调用泄漏
        evaluate("let z = 1 in z")
        with self.assertRaises(NameError):
            evaluate("z")


if __name__ == "__main__":
    unittest.main()
