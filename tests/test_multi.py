"""Matcher 现有朴素行为的锁定测试（基线，改造时一字不许改）。"""

import unittest

from acx.multi import Erro, Matcher, build


class TestFindAll(unittest.TestCase):
    def test_single_hit(self):
        m = Matcher(["he"])
        self.assertEqual(m.find_all("she"), {"he": [1]})

    def test_multiple_hits_ascending(self):
        m = Matcher(["aa"])
        self.assertEqual(m.find_all("aaaa"), {"aa": [0, 1, 2]})

    def test_multiple_patterns(self):
        m = Matcher(["he", "she", "hers"])
        self.assertEqual(
            m.find_all("ushers"),
            {"he": [2], "she": [1], "hers": [2]},
        )

    def test_multiple_patterns_no_hit(self):
        m = Matcher(["he", "she", "him"])
        self.assertEqual(
            m.find_all("ushers"),
            {"he": [2], "she": [1], "him": []},
        )

    def test_pattern_longer_than_text(self):
        m = Matcher(["longpattern"])
        self.assertEqual(m.find_all("short"), {"longpattern": []})

    def test_empty_text(self):
        m = Matcher(["a"])
        self.assertEqual(m.find_all(""), {"a": []})

    def test_empty_pattern_no_hits(self):
        m = Matcher([""])
        self.assertEqual(m.find_all("abc"), {"": []})

    def test_empty_pattern_set(self):
        m = Matcher([])
        self.assertEqual(m.find_all("abc"), {})

    def test_duplicate_pattern_one_key(self):
        m = Matcher(["ab", "ab"])
        self.assertEqual(m.find_all("abab"), {"ab": [0, 2]})

    def test_prefix_pattern(self):
        m = Matcher(["a", "ab"])
        self.assertEqual(m.find_all("ab"), {"a": [0], "ab": [0]})


class TestSinglePatternApi(unittest.TestCase):
    def test_find(self):
        m = Matcher(["ab"])
        self.assertEqual(m.find("ab", "xabab"), [1, 3])

    def test_count(self):
        m = Matcher(["ab"])
        self.assertEqual(m.count("ab", "ababab"), 3)

    def test_find_unknown_pattern_raises(self):
        m = Matcher(["ab"])
        with self.assertRaises(Erro):
            m.find("zz", "abab")

    def test_patterns_preserved(self):
        m = Matcher(["b", "a"])
        self.assertEqual(m.patterns(), ["b", "a"])


class TestSearchOrdering(unittest.TestCase):
    def test_search_pattern_order(self):
        m = Matcher(["he", "she"])
        self.assertEqual(
            m.search("ushers"),
            [("he", 2), ("she", 1)],
        )

    def test_search_same_pattern_ascending(self):
        m = Matcher(["aa"])
        self.assertEqual(m.search("aaaa"), [("aa", 0), ("aa", 1), ("aa", 2)])

    def test_search_empty_pattern_set(self):
        m = Matcher([])
        self.assertEqual(m.search("anything"), [])

    def test_total(self):
        m = Matcher(["he", "she"])
        self.assertEqual(m.total("ushers"), 2)


class TestDeterminism(unittest.TestCase):
    def test_repeat_runs_identical(self):
        m = Matcher(["he", "she", "hers", ""])
        first = m.search("ushers")
        for _ in range(5):
            self.assertEqual(m.search("ushers"), first)

    def test_build_helper(self):
        self.assertEqual(build(["ab"], "abab"), [("ab", 0), ("ab", 2)])


class TestExceptionBase(unittest.TestCase):
    def test_erro_is_exception(self):
        self.assertTrue(issubclass(Erro, Exception))


if __name__ == "__main__":
    unittest.main()
