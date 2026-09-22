"""解析模块现有行为的锁定测试。"""

import unittest

from rexflow import PatternError, parse
from rexflow.parser import Char, Seq, Star


class TestParseTree(unittest.TestCase):
    def test_literals_become_char_nodes(self):
        ast = parse("abc")
        self.assertIsInstance(ast, Seq)
        self.assertEqual(len(ast.children), 3)
        self.assertTrue(all(isinstance(n, Char) for n in ast.children))
        self.assertEqual([n.ch for n in ast.children], ["a", "b", "c"])

    def test_star_wraps_previous_char(self):
        ast = parse("ab*")
        self.assertIsInstance(ast.children[0], Char)
        star = ast.children[1]
        self.assertIsInstance(star, Star)
        self.assertIsInstance(star.child, Char)
        self.assertEqual(star.child.ch, "b")

    def test_empty_pattern_is_empty_seq(self):
        ast = parse("")
        self.assertIsInstance(ast, Seq)
        self.assertEqual(ast.children, ())

    def test_children_is_tuple(self):
        self.assertIsInstance(parse("a*").children, tuple)


class TestParseErrors(unittest.TestCase):
    def test_star_without_operand(self):
        with self.assertRaises(PatternError) as ctx:
            parse("*a")
        self.assertEqual(ctx.exception.pos, 0)

    def test_double_star_points_at_second(self):
        with self.assertRaises(PatternError) as ctx:
            parse("ab**")
        self.assertEqual(ctx.exception.pos, 3)

    def test_unmatched_paren_reports_position(self):
        with self.assertRaises(PatternError) as ctx:
            parse("a)b")
        self.assertEqual(ctx.exception.pos, 1)
        self.assertEqual(ctx.exception.pattern, "a)b")

    def test_unclosed_class_reports_position(self):
        with self.assertRaises(PatternError) as ctx:
            parse("ab[")
        self.assertEqual(ctx.exception.pos, 2)

    def test_error_message_carries_pointer_line(self):
        with self.assertRaises(PatternError) as ctx:
            parse("ab[")
        message = str(ctx.exception)
        self.assertIn("位置 2", message)
        self.assertTrue(message.rstrip().endswith("^"))

    def test_error_is_value_error(self):
        self.assertTrue(issubclass(PatternError, ValueError))


if __name__ == "__main__":
    unittest.main()
