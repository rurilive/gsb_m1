"""regex 操作符与 not() 组合器的行为测试。"""

import unittest

from flagr import RuleCompileError, compile_rules


def compile_one(rule_line):
    return compile_rules(f"flag t\n{rule_line}\ndefault off\n")


class TestRegex(unittest.TestCase):
    def test_regex_hit(self):
        engine = compile_one('when email regex "^.*@corp\\." -> on\n')
        d = engine.evaluate("t", {"email": "ada@corp.example"})
        self.assertTrue(d.enabled)
        self.assertEqual(d.source, "rule#1")

    def test_regex_miss(self):
        engine = compile_one('when email regex "^.*@corp\\." -> on\n')
        d = engine.evaluate("t", {"email": "ada@gmail.com"})
        self.assertFalse(d.enabled)
        self.assertEqual(d.source, "default")

    def test_regex_missing_field_is_miss(self):
        engine = compile_one('when email regex "^.*@corp\\." -> on\n')
        self.assertFalse(engine.evaluate("t", {}).enabled)

    def test_regex_describe(self):
        engine = compile_one('when email regex "^.*@corp\\." -> on\n')
        d = engine.evaluate("t", {"email": "ada@corp.example"})
        self.assertEqual(d.trace[0][1], 'email regex "^.*@corp\\."')

    def test_invalid_pattern_error_position(self):
        text = 'flag t\nwhen email regex "[" -> on\ndefault off\n'
        with self.assertRaises(RuleCompileError) as cm:
            compile_rules(text)
        self.assertEqual((cm.exception.line, cm.exception.col), (2, 18))

    def test_invalid_pattern_rejected_at_compile_time(self):
        # 第二条规则永远不会被求值（第一条恒命中），非法正则仍在编译期报错
        text = (
            "flag t\n"
            "when age gt 0 -> on\n"
            'when email regex "(unclosed" -> off\n'
            "default off\n"
        )
        with self.assertRaises(RuleCompileError) as cm:
            compile_rules(text)
        self.assertEqual((cm.exception.line, cm.exception.col), (3, 18))

    def test_regex_pattern_must_be_string(self):
        with self.assertRaises(RuleCompileError) as cm:
            compile_one("when email regex 123 -> on\n")
        self.assertIn("字符串", cm.exception.message)


class TestNot(unittest.TestCase):
    def test_not_inverts_clause(self):
        engine = compile_one("when not(country eq CN) -> on\n")
        self.assertFalse(engine.evaluate("t", {"country": "CN"}).enabled)
        self.assertTrue(engine.evaluate("t", {"country": "JP"}).enabled)

    def test_not_nested_with_regex(self):
        engine = compile_one(
            'when and(age ge 18, not(email regex "^.*@corp\\.")) -> on\n')
        hit = engine.evaluate("t", {"age": 30, "email": "ada@gmail.com"})
        self.assertTrue(hit.enabled)
        miss = engine.evaluate("t", {"age": 30, "email": "ada@corp.example"})
        self.assertFalse(miss.enabled)

    def test_not_inside_not(self):
        engine = compile_one("when not(not(country eq CN)) -> on\n")
        self.assertTrue(engine.evaluate("t", {"country": "CN"}).enabled)
        self.assertFalse(engine.evaluate("t", {"country": "JP"}).enabled)

    def test_not_describe(self):
        engine = compile_one(
            'when not(email regex "^.*@corp\\.") -> on\n')
        d = engine.evaluate("t", {"email": "ada@gmail.com"})
        self.assertEqual(
            d.trace[0][1], 'not(email regex "^.*@corp\\.")')

    def test_not_rejects_multiple_args(self):
        with self.assertRaises(RuleCompileError) as cm:
            compile_one("when not(age gt 0, age lt 99) -> on\n")
        self.assertIn("not", cm.exception.message)


if __name__ == "__main__":
    unittest.main()
