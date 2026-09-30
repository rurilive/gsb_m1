"""exprparse 基线测试：锁住改造前朴素反复扫描实现的现有行为。"""

import unittest

from exprparse.engine import (
    Expression,
    ExprError,
    InvalidSyntaxError,
    UnbalancedParenError,
    DivisionByZeroError,
    UnknownVariableError,
    EmptyExpressionError,
)


class TestEvaluate(unittest.TestCase):
    def setUp(self):
        self.ev = Expression()

    def test_precedence(self):
        self.assertEqual(self.ev.evaluate("1+2*3"), 7)
        self.assertEqual(self.ev.evaluate("2*3+1"), 7)
        self.assertEqual(self.ev.evaluate("1+2-3"), 0)

    def test_left_associative(self):
        self.assertEqual(self.ev.evaluate("2-3-4"), -5)
        self.assertEqual(self.ev.evaluate("8/4/2"), 1)

    def test_parens(self):
        self.assertEqual(self.ev.evaluate("(1+2)*3"), 9)
        self.assertEqual(self.ev.evaluate("((1+2)*(3+4))-5"), 16)
        self.assertEqual(self.ev.evaluate("(((7)))"), 7)

    def test_floor_division(self):
        self.assertEqual(self.ev.evaluate("10/3"), 3)
        self.assertEqual(self.ev.evaluate("0/5"), 0)
        self.assertEqual(self.ev.evaluate("7/-2"), -4)

    def test_unary(self):
        self.assertEqual(self.ev.evaluate("-5+10"), 5)
        self.assertEqual(self.ev.evaluate("-(3+4)"), -7)
        self.assertEqual(self.ev.evaluate("2*-3"), -6)
        self.assertEqual(self.ev.evaluate("-(-5)"), 5)
        self.assertEqual(self.ev.evaluate("+9"), 9)

    def test_variables(self):
        variables = {"a": 2, "b": 5, "c": 1}
        self.assertEqual(self.ev.evaluate("a*b+c", variables), 11)
        self.assertEqual(self.ev.evaluate("a-b", {"a": 10, "b": 3}), 7)
        self.assertEqual(self.ev.evaluate("(a+c)*(b-c)", variables), 12)

    def test_whitespace_ignored(self):
        self.assertEqual(self.ev.evaluate(" 1 + 2 * 3 "), 7)

    def test_deterministic(self):
        first = self.ev.evaluate("(1+2)*(3-4)")
        second = self.ev.evaluate("(1+2)*(3-4)")
        self.assertEqual(first, second)


class TestToRpn(unittest.TestCase):
    def setUp(self):
        self.ev = Expression()

    def test_simple(self):
        self.assertEqual(self.ev.to_rpn("1+2*3"), [1, 2, 3, "*", "+"])

    def test_parens(self):
        self.assertEqual(self.ev.to_rpn("(1+2)*3"), [1, 2, "+", 3, "*"])

    def test_unary_marker(self):
        self.assertEqual(self.ev.to_rpn("2*-3"), [2, 3, "u", "*"])
        self.assertEqual(self.ev.to_rpn("-(-5)"), [5, "u", "u"])

    def test_left_associative(self):
        self.assertEqual(self.ev.to_rpn("1+2+3"), [1, 2, "+", 3, "+"])

    def test_only_nonnegative_integers(self):
        with self.assertRaises(InvalidSyntaxError):
            self.ev.to_rpn("x+1")


class TestBatch(unittest.TestCase):
    def setUp(self):
        self.ev = Expression()

    def test_results_and_argmax(self):
        results, best = self.ev.batch_evaluate(["1+1", "3*3", "10-4"], {})
        self.assertEqual(results, [2, 9, 6])
        self.assertEqual(best, 1)

    def test_tie_takes_smallest_index(self):
        results, best = self.ev.batch_evaluate(["1+1", "2", "3-1"], {})
        self.assertEqual(results, [2, 2, 2])
        self.assertEqual(best, 0)

    def test_empty_batch(self):
        with self.assertRaises(EmptyExpressionError):
            self.ev.batch_evaluate([], {})


class TestScanCount(unittest.TestCase):
    def setUp(self):
        self.ev = Expression()

    def test_scan_count_resets(self):
        self.ev.evaluate("1+2")
        first = self.ev.scan_count()
        self.ev.evaluate("3")
        self.assertLess(self.ev.scan_count(), first)

    def test_scan_grows_with_depth(self):
        previous = -1
        for depth in (1, 2, 4, 8, 16):
            self.ev.evaluate("(" * depth + "7" + ")" * depth)
            current = self.ev.scan_count()
            self.assertGreater(current, previous)
            previous = current


class TestErrors(unittest.TestCase):
    def setUp(self):
        self.ev = Expression()

    def test_empty_expression(self):
        for bad in ["", "   "]:
            with self.assertRaises(EmptyExpressionError):
                self.ev.evaluate(bad)

    def test_unbalanced_parens(self):
        for bad in ["(1+2", "1+2)", "((1+2)", "1+2))"]:
            with self.assertRaises(UnbalancedParenError):
                self.ev.evaluate(bad)

    def test_division_by_zero(self):
        for bad in ["1/0", "5/(3-3)"]:
            with self.assertRaises(DivisionByZeroError):
                self.ev.evaluate(bad)

    def test_unknown_variable(self):
        with self.assertRaises(UnknownVariableError):
            self.ev.evaluate("x+1", {})

    def test_invalid_syntax(self):
        for bad in ["1+*2", "*3", "1+", "+"]:
            with self.assertRaises(InvalidSyntaxError):
                self.ev.evaluate(bad)

    def test_all_errors_share_base(self):
        for bad in ["", "(1+2", "1/0", "x+1", "1+*2"]:
            with self.assertRaises(ExprError):
                self.ev.evaluate(bad)


if __name__ == "__main__":
    unittest.main()
