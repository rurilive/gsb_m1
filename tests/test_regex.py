"""regex 匹配器与 not() 组合器的行为测试。"""
import unittest

from flagr import RuleCompileError, compile_rules


def compile_one(rule_line):
    return compile_rules(f"flag t\n{rule_line}\ndefault off\n")


class TestRegexMatcher(unittest.TestCase):
    def test_regex_hit_and_miss(self):
        engine = compile_one('when email regex "^.*@corp\\." -> on\n')
        self.assertTrue(
            engine.evaluate("t", {"email": "ada@corp.example"}).enabled)
        self.assertFalse(
            engine.evaluate("t", {"email": "ada@example.com"}).enabled)

    def test_regex_is_search_not_fullmatch(self):
        engine = compile_one('when path regex "/admin/" -> on\n')
        self.assertTrue(
            engine.evaluate("t", {"path": "/api/admin/users"}).enabled)
        self.assertFalse(engine.evaluate("t", {"path": "/api/users"}).enabled)

    def test_regex_missing_or_nonstr_field_is_miss(self):
        engine = compile_one('when email regex "corp" -> on\n')
        self.assertFalse(engine.evaluate("t", {}).enabled)
        self.assertFalse(engine.evaluate("t", {"email": 42}).enabled)
        self.assertFalse(engine.evaluate("t", {"email": True}).enabled)

    def test_regex_describe(self):
        engine = compile_one('when email regex "^.*@corp\\." -> on\n')
        self.assertEqual(
            engine.spec("t").rules[0].matcher.describe(),
            'email regex "^.*@corp\\."',
        )

    def test_invalid_pattern_error_points_at_pattern_token(self):
        with self.assertRaises(RuleCompileError) as cm:
            compile_rules(
                'flag a\nwhen email regex "^[a-z" -> on\ndefault off\n')
        self.assertEqual(cm.exception.line, 2)
        self.assertEqual(cm.exception.col, 18)
        self.assertIn("非法正则", cm.exception.message)

    def test_invalid_pattern_rejected_at_compile_even_if_never_evaluated(self):
        # 非法 pattern 排在永不命中的规则之后，且开关从不求值，编译期仍报错
        text = (
            "flag a\n"
            "when x eq 1 -> on\n"
            'when email regex "(" -> off\n'
            "default off\n"
        )
        with self.assertRaises(RuleCompileError) as cm:
            compile_rules(text)
        self.assertEqual((cm.exception.line, cm.exception.col), (3, 18))

    def test_regex_pattern_must_be_string(self):
        with self.assertRaises(RuleCompileError) as cm:
            compile_rules("flag a\nwhen email regex 123 -> on\n")
        self.assertEqual((cm.exception.line, cm.exception.col), (2, 18))


class TestNotCombinator(unittest.TestCase):
    def test_not_basic(self):
        engine = compile_one("when not(country eq CN) -> on\n")
        self.assertTrue(engine.evaluate("t", {"country": "US"}).enabled)
        self.assertFalse(engine.evaluate("t", {"country": "CN"}).enabled)

    def test_not_inverts_missing_field_miss(self):
        engine = compile_one("when not(vip eq true) -> on\n")
        self.assertTrue(engine.evaluate("t", {}).enabled)
        self.assertFalse(engine.evaluate("t", {"vip": True}).enabled)

    def test_not_nested_in_and_or(self):
        engine = compile_one(
            "when and(not(plan eq free), or(age ge 18, vip eq true)) -> on\n")
        self.assertTrue(
            engine.evaluate("t", {"plan": "pro", "age": 20}).enabled)
        self.assertFalse(
            engine.evaluate("t", {"plan": "free", "age": 20}).enabled)
        self.assertFalse(
            engine.evaluate("t", {"plan": "pro", "age": 10}).enabled)

    def test_not_nested_not(self):
        engine = compile_one("when not(not(x eq 1)) -> on\n")
        self.assertTrue(engine.evaluate("t", {"x": 1}).enabled)
        self.assertFalse(engine.evaluate("t", {"x": 2}).enabled)

    def test_not_with_regex(self):
        engine = compile_one('when not(email regex "@corp\\.") -> on\n')
        self.assertTrue(
            engine.evaluate("t", {"email": "ada@example.com"}).enabled)
        self.assertFalse(
            engine.evaluate("t", {"email": "ada@corp.example"}).enabled)

    def test_regex_and_not_nested_in_or(self):
        engine = compile_one(
            'when or(vip eq true, not(email regex "@corp\\.")) -> on\n')
        self.assertTrue(engine.evaluate(
            "t", {"vip": True, "email": "ada@corp.example"}).enabled)
        self.assertTrue(
            engine.evaluate("t", {"email": "ada@example.com"}).enabled)
        self.assertFalse(
            engine.evaluate("t", {"email": "ada@corp.example"}).enabled)

    def test_not_describe(self):
        engine = compile_one(
            "when not(and(plan eq pro, not(age lt 18))) -> on\n")
        self.assertEqual(
            engine.spec("t").rules[0].matcher.describe(),
            'not(and(plan eq "pro", not(age lt 18)))',
        )

    def test_not_arity_must_be_exactly_one(self):
        with self.assertRaises(RuleCompileError) as cm:
            compile_rules("flag a\nwhen not(x eq 1, y eq 2) -> on\n")
        self.assertEqual((cm.exception.line, cm.exception.col), (2, 6))
        self.assertIn("not 需要恰好 1 个参数", cm.exception.message)


if __name__ == "__main__":
    unittest.main()
