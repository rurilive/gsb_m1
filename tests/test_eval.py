"""eval 现有行为的锁定测试：四则运算、括号、一元正负、取模、变量取值与错误。

只覆盖当前实现已经具备的能力。依赖跟踪、记忆化失效、副作用记录与重放、
惰性短路、事务回滚与并发隔离都还没有，新增行为另建测试文件，不改动本文件。
"""

import unittest

from effecteval import EvalRuntimeError, ParseError, eval


class TestArithmetic(unittest.TestCase):
    def test_int_addition(self):
        self.assertEqual(eval("1 + 2"), 3)

    def test_subtraction_is_left_associative(self):
        self.assertEqual(eval("10 - 3 - 2"), 5)

    def test_multiplication_binds_tighter_than_addition(self):
        self.assertEqual(eval("1 + 2 * 3"), 7)

    def test_parentheses_override_precedence(self):
        self.assertEqual(eval("(1 + 2) * 3"), 9)

    def test_nested_parentheses(self):
        self.assertEqual(eval("((1 + 2) * (3 + 4))"), 21)

    def test_division_yields_float(self):
        self.assertEqual(eval("7 / 2"), 3.5)

    def test_division_is_left_associative(self):
        self.assertEqual(eval("8 / 4 / 2"), 1.0)

    def test_modulo(self):
        self.assertEqual(eval("17 % 5"), 2)

    def test_float_literal(self):
        self.assertEqual(eval("2.5 * 2"), 5.0)

    def test_leading_decimal_point(self):
        self.assertEqual(eval(".5 + .5"), 1.0)

    def test_whitespace_is_ignored(self):
        self.assertEqual(eval("  1+2*3  "), 7)

    def test_negative_literal(self):
        self.assertEqual(eval("-3 + 4"), 1)

    def test_unary_minus_on_parenthesized(self):
        self.assertEqual(eval("-(2 + 3)"), -5)

    def test_double_unary(self):
        self.assertEqual(eval("--4"), 4)

    def test_unary_plus(self):
        self.assertEqual(eval("+7"), 7)

    def test_unary_binds_tighter_than_multiply(self):
        self.assertEqual(eval("-2 * 3"), -6)


class TestVariables(unittest.TestCase):
    def test_variable_from_dict(self):
        self.assertEqual(eval("x + 1", {"x": 2}), 3)

    def test_expression_over_variables(self):
        self.assertEqual(eval("a * b - c", {"a": 3, "b": 4, "c": 2}), 10)

    def test_repeated_variable(self):
        self.assertEqual(eval("x * x", {"x": 5}), 25)

    def test_env_none_rejects_every_variable(self):
        with self.assertRaises(EvalRuntimeError):
            eval("x")

    def test_undefined_variable(self):
        with self.assertRaises(EvalRuntimeError) as ctx:
            eval("1 + total", {"x": 1})
        self.assertEqual(ctx.exception.index, 4)

    def test_env_is_not_mutated(self):
        env = {"x": 1}
        eval("x + 1", env)
        self.assertEqual(env, {"x": 1})


class TestEvalErrors(unittest.TestCase):
    def test_division_by_zero(self):
        with self.assertRaises(EvalRuntimeError) as ctx:
            eval("1 / 0")
        self.assertEqual(ctx.exception.index, 2)

    def test_modulo_by_zero(self):
        with self.assertRaises(EvalRuntimeError) as ctx:
            eval("9 % 0")
        self.assertEqual(ctx.exception.index, 2)

    def test_division_by_computed_zero(self):
        with self.assertRaises(EvalRuntimeError):
            eval("6 / (3 - 3)")

    def test_error_carries_source(self):
        with self.assertRaises(EvalRuntimeError) as ctx:
            eval("1 / 0")
        self.assertEqual(ctx.exception.src, "1 / 0")

    def test_error_message_is_single_line(self):
        with self.assertRaises(EvalRuntimeError) as ctx:
            eval("1 + 2 / 0")
        self.assertNotIn("\n", ctx.exception.message)

    def test_parse_error_for_dangling_operator(self):
        with self.assertRaises(ParseError):
            eval("1 +")

    def test_parse_error_for_unclosed_paren(self):
        with self.assertRaises(ParseError):
            eval("(1 + 2")

    def test_parse_error_for_empty(self):
        with self.assertRaises(ParseError):
            eval("   ")

    def test_parse_error_for_unbalanced_close(self):
        with self.assertRaises(ParseError):
            eval("1 + 2)")

    def test_parse_error_for_pending_operator(self):
        with self.assertRaises(ParseError):
            eval("1 == 2")


if __name__ == "__main__":
    unittest.main()