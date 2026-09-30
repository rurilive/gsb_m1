"""FlatPrefixSet 基线行为测试。

锁住改造前的朴素现状: 插入、删除、前缀判定与计数、完整单词判定、
按字典序输出、最长公共前缀、通配符匹配与异常口径。本文件在改造后
一字不许改, 且必须一直全绿。
"""

import unittest

from triex2.trie import (
    EmptyError,
    FlatPrefixSet,
    NotFoundError,
    TrieError,
)


def build(words):
    """按给定顺序插入一串单词, 返回基线集合。"""
    s = FlatPrefixSet()
    for w in words:
        s.insert(w)
    return s


class TestBasics(unittest.TestCase):
    def test_empty(self):
        s = FlatPrefixSet()
        self.assertEqual(len(s), 0)
        self.assertEqual(s.all_words(), [])
        self.assertEqual(s.count_prefix(""), 0)
        self.assertFalse(s.has_prefix("a"))
        self.assertFalse(s.contains("a"))

    def test_insert_and_len(self):
        s = build(["app", "apple", "app"])
        self.assertEqual(len(s), 3)

    def test_insert_duplicates_kept_by_count(self):
        s = build(["x", "x", "x"])
        self.assertEqual(len(s), 3)
        self.assertEqual(s.count_prefix("x"), 3)

    def test_insert_rejects_non_str(self):
        s = FlatPrefixSet()
        with self.assertRaises(TrieError):
            s.insert(3)
        with self.assertRaises(TrieError):
            s.insert(None)

    def test_empty_string_roundtrip(self):
        s = FlatPrefixSet()
        s.insert("")
        self.assertEqual(len(s), 1)
        self.assertTrue(s.contains(""))
        self.assertTrue(s.has_prefix(""))


class TestPrefixQueries(unittest.TestCase):
    def setUp(self):
        self.s = build(["app", "apple", "app", "apricot", "bat", "banana", "band"])

    def test_has_prefix(self):
        self.assertTrue(self.s.has_prefix("app"))
        self.assertTrue(self.s.has_prefix("ba"))
        self.assertTrue(self.s.has_prefix(""))
        self.assertFalse(self.s.has_prefix("cat"))
        self.assertFalse(self.s.has_prefix("apples"))

    def test_count_prefix(self):
        self.assertEqual(self.s.count_prefix("app"), 3)
        self.assertEqual(self.s.count_prefix("ap"), 4)
        self.assertEqual(self.s.count_prefix("b"), 3)
        self.assertEqual(self.s.count_prefix(""), 7)
        self.assertEqual(self.s.count_prefix("z"), 0)

    def test_prefix_whole_word_counts_itself(self):
        self.assertEqual(self.s.count_prefix("apple"), 1)
        self.assertTrue(self.s.has_prefix("apple"))

    def test_words_with_prefix(self):
        self.assertEqual(
            self.s.words_with_prefix("ap"),
            ["app", "app", "apple", "apricot"],
        )
        self.assertEqual(self.s.words_with_prefix("zzz"), [])

    def test_words_with_prefix_is_a_copy(self):
        got = self.s.words_with_prefix("ap")
        got.append("junk")
        self.assertEqual(len(self.s), 7)


class TestContains(unittest.TestCase):
    def test_contains(self):
        s = build(["app", "apple"])
        self.assertTrue(s.contains("app"))
        self.assertTrue(s.contains("apple"))
        self.assertFalse(s.contains("appl"))
        self.assertFalse(s.contains("apples"))
        self.assertFalse(s.contains(""))


class TestOrdering(unittest.TestCase):
    def test_all_words_sorted(self):
        s = build(["bat", "app", "banana", "apple", "band", "app", "apricot"])
        self.assertEqual(
            s.all_words(),
            ["app", "app", "apple", "apricot", "banana", "band", "bat"],
        )

    def test_all_words_is_a_copy(self):
        s = build(["b", "a"])
        got = s.all_words()
        got.append("c")
        self.assertEqual(s.all_words(), ["a", "b"])


class TestLongestCommonPrefix(unittest.TestCase):
    def test_empty_raises(self):
        with self.assertRaises(EmptyError):
            FlatPrefixSet().longest_common_prefix()

    def test_single(self):
        self.assertEqual(build(["abc"]).longest_common_prefix(), "abc")

    def test_shared(self):
        self.assertEqual(
            build(["flower", "flow", "flight"]).longest_common_prefix(), "fl"
        )

    def test_all_equal(self):
        self.assertEqual(build(["dog", "dog", "dog"]).longest_common_prefix(), "dog")

    def test_prefix_of_other(self):
        self.assertEqual(build(["ab", "abc"]).longest_common_prefix(), "ab")

    def test_no_common(self):
        self.assertEqual(build(["dog", "cat"]).longest_common_prefix(), "")


class TestPattern(unittest.TestCase):
    def setUp(self):
        self.s = build(["app", "apple", "app", "apricot", "bat", "banana", "band"])

    def test_dot_matches_one(self):
        self.assertEqual(self.s.match_pattern("app.e"), ["apple"])

    def test_all_wild(self):
        self.assertEqual(self.s.match_pattern("..."), ["app", "app", "bat"])

    def test_literal_only(self):
        self.assertEqual(self.s.match_pattern("ban"), [])

    def test_mixed(self):
        self.assertEqual(self.s.match_pattern("ban.n."), ["banana"])

    def test_no_match(self):
        self.assertEqual(self.s.match_pattern("zzz"), [])

    def test_rejects_non_str(self):
        with self.assertRaises(TrieError):
            self.s.match_pattern(5)


class TestRemove(unittest.TestCase):
    def test_remove_one_of_duplicates(self):
        s = build(["app", "app", "bat"])
        s.remove("app")
        self.assertEqual(len(s), 2)
        self.assertTrue(s.contains("app"))
        self.assertEqual(s.count_prefix("app"), 1)

    def test_remove_absent_raises(self):
        s = build(["app"])
        with self.assertRaises(NotFoundError):
            s.remove("bat")

    def test_remove_rejects_non_str(self):
        s = build(["app"])
        with self.assertRaises(TrieError):
            s.remove(7)

    def test_remove_to_empty(self):
        s = build(["a"])
        s.remove("a")
        self.assertEqual(len(s), 0)
        self.assertEqual(s.all_words(), [])


class TestExceptionHierarchy(unittest.TestCase):
    def test_all_inherit_base(self):
        self.assertTrue(issubclass(EmptyError, TrieError))
        self.assertTrue(issubclass(NotFoundError, TrieError))
        self.assertTrue(issubclass(TrieError, Exception))


class TestDeterminism(unittest.TestCase):
    def test_repeat_same_result(self):
        words = ["banana", "app", "band", "apple", "bat", "app"]
        a = build(words)
        b = build(words)
        self.assertEqual(a.all_words(), b.all_words())
        self.assertEqual(a.count_prefix("app"), b.count_prefix("app"))
        self.assertEqual(
            a.longest_common_prefix(), b.longest_common_prefix()
        )


if __name__ == "__main__":
    unittest.main()
