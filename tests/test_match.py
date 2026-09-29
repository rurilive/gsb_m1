"""regexlab 现有字面量行为的锁定测试。

这一组用例只锁住改造前就成立、改造后也必须继续成立的事实：模式
里不含任何语法元字符、且输入串与模式整段相等时算命中，match 给出
起止跨度；输入串与模式不相等时一律判不中，返回 None。
"""

import unittest

from regexlab import LiteralMatch, match


class TestLiteralMatchClass(unittest.TestCase):
    def test_exact_equality_hits(self):
        self.assertTrue(LiteralMatch("abc").test("abc"))

    def test_unequal_text_misses(self):
        self.assertFalse(LiteralMatch("abc").test("xyz"))

    def test_empty_pattern_tests_empty_text(self):
        self.assertTrue(LiteralMatch("").test(""))

    def test_empty_pattern_rejects_nonempty_text(self):
        self.assertFalse(LiteralMatch("").test("a"))

    def test_unicode_literal_hits(self):
        self.assertTrue(LiteralMatch("héllo").test("héllo"))


class TestLiteralMatchSpan(unittest.TestCase):
    def test_span_is_whole_text_on_hit(self):
        self.assertEqual(LiteralMatch("hello").span("hello"), (0, 5))

    def test_span_is_pair_of_ints(self):
        span = LiteralMatch("abc").span("abc")
        self.assertIsInstance(span, tuple)
        self.assertEqual([type(v) for v in span], [int, int])

    def test_span_none_on_miss(self):
        self.assertIsNone(LiteralMatch("abc").span("xyz"))

    def test_whitespace_is_significant(self):
        self.assertTrue(LiteralMatch("a b").test("a b"))


class TestModuleMatch(unittest.TestCase):
    def test_match_uses_literal_equality(self):
        self.assertEqual(match("abc", "abc"), (0, 3))

    def test_match_returns_none_on_miss(self):
        self.assertIsNone(match("abc", "xyz"))

    def test_match_empty_text_misses_nonempty_pattern(self):
        self.assertIsNone(match("abc", ""))

    def test_match_pattern_nowhere_in_text(self):
        # 改造前后一致：模式没在文本里整段出现，就是判不中。
        self.assertIsNone(match("abc", "abxabx"))


if __name__ == "__main__":
    unittest.main()
