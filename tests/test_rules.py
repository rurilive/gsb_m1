"""flagr 现有行为的锁定测试。"""

import unittest

from flagr import (
    Decision,
    RuleCompileError,
    UnknownFlagError,
    compile_rules,
)

RULES = """\
# 网关灰度规则
flag checkout-v2
when and(country in [CN, US], plan eq pro) -> on
default off

flag beta-ui
when or(vip eq true, age ge 18) -> on
default off
"""

CTX = {"country": "CN", "plan": "pro", "vip": False, "age": 17}


def compile_one(rule_line):
    return compile_rules(f"flag t\n{rule_line}\ndefault off\n")


class TestCompileAndEvaluate(unittest.TestCase):
    def test_flags_listing(self):
        engine = compile_rules(RULES)
        self.assertEqual(engine.flags, ["checkout-v2", "beta-ui"])

    def test_and_rule_hit(self):
        d = compile_rules(RULES).evaluate("checkout-v2", CTX)
        self.assertTrue(d.enabled)
        self.assertEqual(d.source, "rule#1")
        self.assertEqual(d.matched, 1)

    def test_and_rule_miss_goes_default(self):
        d = compile_rules(RULES).evaluate("checkout-v2", {"country": "JP"})
        self.assertFalse(d.enabled)
        self.assertEqual(d.source, "default")
        self.assertIsNone(d.matched)

    def test_or_rule_hit(self):
        d = compile_rules(RULES).evaluate("beta-ui", {"age": 30})
        self.assertTrue(d.enabled)

    def test_first_match_wins(self):
        engine = compile_one("when age ge 18 -> off\nwhen age gt 0 -> on\n")
        d = engine.evaluate("t", {"age": 30})
        self.assertFalse(d.enabled)
        self.assertEqual(d.source, "rule#1")

    def test_no_default_means_off(self):
        engine = compile_rules("flag t\nwhen x eq 1 -> on\n")
        self.assertFalse(engine.evaluate("t", {}).enabled)

    def test_unknown_flag_raises(self):
        with self.assertRaises(UnknownFlagError):
            compile_rules(RULES).evaluate("nope", {})

    def test_missing_field_is_miss_for_all_ops(self):
        engine = compile_one("when a eq 1 -> on\n")
        self.assertFalse(engine.evaluate("t", {}).enabled)
        engine = compile_one("when a ne 1 -> on\n")
        self.assertFalse(engine.evaluate("t", {}).enabled)
        engine = compile_one("when a in [1, 2] -> on\n")
        self.assertFalse(engine.evaluate("t", {}).enabled)
        engine = compile_one("when a contains x -> on\n")
        self.assertFalse(engine.evaluate("t", {}).enabled)
        engine = compile_one("when a gt 0 -> on\n")
        self.assertFalse(engine.evaluate("t", {}).enabled)


class TestMatcherSemantics(unittest.TestCase):
    def test_eq_typed(self):
        engine = compile_one("when n eq 18 -> on\n")
        self.assertTrue(engine.evaluate("t", {"n": 18}).enabled)
        self.assertTrue(engine.evaluate("t", {"n": 18.0}).enabled)
        self.assertFalse(engine.evaluate("t", {"n": "18"}).enabled)
        self.assertFalse(engine.evaluate("t", {"n": True}).enabled)

    def test_eq_bool(self):
        engine = compile_one("when vip eq true -> on\n")
        self.assertTrue(engine.evaluate("t", {"vip": True}).enabled)
        self.assertFalse(engine.evaluate("t", {"vip": 1}).enabled)

    def test_ne(self):
        engine = compile_one("when plan ne pro -> on\n")
        self.assertTrue(engine.evaluate("t", {"plan": "free"}).enabled)
        self.assertFalse(engine.evaluate("t", {"plan": "pro"}).enabled)

    def test_in_set(self):
        engine = compile_one("when country in [CN, US] -> on\n")
        self.assertTrue(engine.evaluate("t", {"country": "US"}).enabled)
        self.assertFalse(engine.evaluate("t", {"country": "JP"}).enabled)

    def test_contains_substring(self):
        engine = compile_one('when email contains "@corp.example.com" -> on\n')
        self.assertTrue(engine.evaluate("t", {"email": "a@corp.example.com"}).enabled)
        self.assertFalse(engine.evaluate("t", {"email": "a@example.com"}).enabled)

    def test_compare_boundaries(self):
        engine = compile_one("when age ge 18 -> on\n")
        self.assertTrue(engine.evaluate("t", {"age": 18}).enabled)
        self.assertFalse(engine.evaluate("t", {"age": 17.9}).enabled)
        engine = compile_one("when age lt 18 -> on\n")
        self.assertTrue(engine.evaluate("t", {"age": 17}).enabled)

    def test_compare_non_numeric_ctx_miss(self):
        engine = compile_one("when age gt 0 -> on\n")
        self.assertFalse(engine.evaluate("t", {"age": "old"}).enabled)
        self.assertFalse(engine.evaluate("t", {"age": True}).enabled)

    def test_nested_combinators(self):
        engine = compile_one(
            "when or(vip eq true, and(country eq CN, age ge 18)) -> on\n")
        self.assertTrue(engine.evaluate("t", {"vip": True}).enabled)
        self.assertTrue(engine.evaluate("t", {"country": "CN", "age": 20}).enabled)
        self.assertFalse(engine.evaluate("t", {"country": "CN", "age": 5}).enabled)

    def test_describe_texts(self):
        engine = compile_rules(RULES)
        self.assertEqual(
            engine.spec("checkout-v2").rules[0].matcher.describe(),
            'and(country in ["CN", "US"], plan eq "pro")',
        )
        self.assertEqual(
            engine.spec("beta-ui").rules[0].matcher.describe(),
            "or(vip eq true, age ge 18)",
        )

    def test_trace_and_explain_golden(self):
        d = compile_rules(RULES).evaluate("beta-ui", {"age": 9})
        self.assertEqual(
            d.explain(),
            "beta-ui -> off (default)\n"
            "  #1 or(vip eq true, age ge 18) miss",
        )
        d2 = compile_rules(RULES).evaluate("beta-ui", {"vip": True})
        self.assertEqual(
            d2.explain(),
            "beta-ui -> on (rule#1)\n"
            "  #1 or(vip eq true, age ge 18) hit",
        )


class TestCompileErrors(unittest.TestCase):
    def assert_error(self, text, line, col, message):
        with self.assertRaises(RuleCompileError) as cm:
            compile_rules(text)
        self.assertEqual(cm.exception.line, line)
        self.assertEqual(cm.exception.col, col)
        self.assertEqual(str(cm.exception), f"{line}:{col}: {message}")
        return cm.exception

    def test_unknown_op_with_position(self):
        self.assert_error(
            "flag a\nwhen country eqx CN -> on\ndefault off\n",
            2, 14, "未知的匹配操作符 'eqx'")

    def test_unknown_combinator_word(self):
        self.assert_error(
            "flag a\nwhen xor(country eq CN, plan eq pro) -> on\n",
            2, 9, "字段 'xor' 后应有操作符，得到 LPAREN")

    def test_combinator_arity(self):
        self.assert_error(
            "flag a\nwhen and(country eq CN) -> on\n",
            2, 6, "and 至少需要 2 个参数")

    def test_numeric_value_required(self):
        self.assert_error(
            "flag a\nwhen country gt pro -> on\n",
            2, 17, "gt 需要数字取值，得到 'pro'")

    def test_unterminated_string(self):
        self.assert_error(
            'flag a\nwhen email contains "abc\n',
            2, 21, "字符串未闭合")

    def test_duplicate_flag(self):
        self.assert_error(
            "flag a\nwhen x eq 1 -> on\nflag a\n",
            3, 1, "重复定义开关 'a'")

    def test_in_missing_bracket(self):
        self.assert_error(
            "flag a\nwhen country in [CN -> on\n",
            2, 21, "in 列表缺少 ]，得到 ARROW")

    def test_missing_expression(self):
        self.assert_error(
            "flag a\nwhen -> on\n",
            2, 6, "应为表达式，得到 ARROW")

    def test_unrecognized_line(self):
        with self.assertRaises(RuleCompileError) as cm:
            compile_rules("foo bar\n")
        self.assertEqual((cm.exception.line, cm.exception.col), (1, 1))


if __name__ == "__main__":
    unittest.main()
