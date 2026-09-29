"""rex 现有字面量行为的锁定测试。

这一组用例只锁住改造前就成立、改造后也必须继续成立的事实：
模式里不含语法元字符、且文本与模式整段相等时算命中，match 给出
起止跨度、search 给出同一个跨度、findall 列出一个命中文本；模式
根本不在文本里出现时一律判不中，返回 None 或空列表。
"""

import unittest

from rex import findall, match, search


class TestMatchLiteral(unittest.TestCase):
    def test_exact_equality_hits(self):
        self.assertEqual(match("abc", "abc"), (0, 3))

    def test_hit_span_is_whole_text(self):
        span = match("hello", "hello")
        self.assertEqual((span[0], span[1]), (0, 5))

    def test_span_is_pair_of_ints(self):
        span = match("abc", "abc")
        self.assertIsInstance(span, tuple)
        self.assertEqual([type(v) for v in span], [int, int])

    def test_unrelated_text_misses(self):
        self.assertIsNone(match("abc", "xyz"))

    def test_empty_text_misses(self):
        self.assertIsNone(match("abc", ""))

    def test_whitespace_is_significant(self):
        self.assertEqual(match("a b", "a b"), (0, 3))

    def test_unicode_literal_hits(self):
        self.assertEqual(match("héllo", "héllo"), (0, 5))


class TestSearchLiteral(unittest.TestCase):
    def test_search_equal_to_match_on_hit(self):
        self.assertEqual(search("abc", "abc"), match("abc", "abc"))

    def test_search_hits_same_span(self):
        self.assertEqual(search("abc", "abc"), (0, 3))

    def test_search_returns_none_when_absent(self):
        self.assertIsNone(search("abc", "xyz"))


class TestFindAllLiteral(unittest.TestCase):
    def test_findall_single_hit(self):
        self.assertEqual(findall("abc", "abc"), ["abc"])

    def test_findall_returns_list(self):
        self.assertIsInstance(findall("abc", "abc"), list)

    def test_findall_empty_when_absent(self):
        self.assertEqual(findall("abc", "xyz"), [])

    def test_findall_empty_when_literal_nowhere_in_text(self):
        # 改造前后一致：模式压根没在文本里出现，就是空列表。
        self.assertEqual(findall("abc", "abxabx"), [])


if __name__ == "__main__":
    unittest.main()
