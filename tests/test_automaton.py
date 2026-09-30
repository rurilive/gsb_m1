"""mpmatch 现有逐模式比对行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from mpmatch.automaton import Erro, Matcher, PatternError


def build_matcher():
    return Matcher(["he", "she", "his", "hers"])


class TestConstruction(unittest.TestCase):
    def test_patterns_kept_in_order(self):
        m = Matcher(["he", "she", "his"])
        self.assertEqual(m.patterns(), ("he", "she", "his"))

    def test_patterns_deduped_keeping_first_order(self):
        m = Matcher(["he", "she", "he"])
        self.assertEqual(m.patterns(), ("he", "she"))

    def test_len_and_contains(self):
        m = build_matcher()
        self.assertEqual(len(m), 4)
        self.assertIn("she", m)
        self.assertNotIn("zzz", m)

    def test_empty_pattern_set_allowed(self):
        m = Matcher([])
        self.assertEqual(m.patterns(), ())
        self.assertEqual(len(m), 0)

    def test_non_sequence_rejected(self):
        with self.assertRaises(PatternError):
            Matcher(7)

    def test_bare_str_rejected(self):
        with self.assertRaises(PatternError):
            Matcher("he")

    def test_non_str_member_rejected(self):
        with self.assertRaises(PatternError):
            Matcher(["he", 7])

    def test_empty_pattern_rejected(self):
        with self.assertRaises(PatternError):
            Matcher(["he", ""])

    def test_pattern_error_is_erro(self):
        self.assertTrue(issubclass(PatternError, Erro))


class TestSearch(unittest.TestCase):
    def test_positions_overlapping(self):
        m = Matcher(["aa"])
        self.assertEqual(m.positions("aa", "aaaa"), [0, 1, 2])

    def test_positions_ascending(self):
        m = build_matcher()
        self.assertEqual(m.positions("he", "he he he"), [0, 3, 6])

    def test_positions_no_hit(self):
        m = build_matcher()
        self.assertEqual(m.positions("hers", "she"), [])

    def test_count_matches_positions(self):
        m = build_matcher()
        text = "ushers"
        for pattern in m.patterns():
            self.assertEqual(m.count(pattern, text), len(m.positions(pattern, text)))

    def test_count_known_values(self):
        m = build_matcher()
        text = "ushers"
        self.assertEqual(m.positions("she", text), [1])
        self.assertEqual(m.positions("he", text), [2])
        self.assertEqual(m.positions("hers", text), [2])

    def test_find_all_returns_every_pattern(self):
        m = build_matcher()
        result = m.find_all("ushers")
        self.assertEqual(sorted(result.keys()), ["he", "hers", "his", "she"])
        self.assertEqual(result["he"], [2])
        self.assertEqual(result["his"], [])

    def test_exists_true_and_false(self):
        m = build_matcher()
        self.assertTrue(m.exists("ushers"))
        self.assertFalse(m.exists("xyz"))

    def test_exists_empty_pattern_set(self):
        m = Matcher([])
        self.assertFalse(m.exists("anything"))
        self.assertEqual(m.find_all("anything"), {})


class TestInputGuards(unittest.TestCase):
    def test_positions_non_str_pattern(self):
        m = build_matcher()
        with self.assertRaises(PatternError):
            m.positions(None, "ushers")

    def test_positions_empty_pattern(self):
        m = build_matcher()
        with self.assertRaises(PatternError):
            m.positions("", "ushers")

    def test_positions_non_str_text(self):
        m = build_matcher()
        with self.assertRaises(PatternError):
            m.positions("he", 7)

    def test_find_all_non_str_text(self):
        m = build_matcher()
        with self.assertRaises(PatternError):
            m.find_all(None)

    def test_exists_non_str_text(self):
        m = build_matcher()
        with self.assertRaises(PatternError):
            m.exists(7)


class TestDeterminism(unittest.TestCase):
    def test_repeated_run_same_result(self):
        m = build_matcher()
        first = m.find_all("ushers his hers")
        for _ in range(3):
            self.assertEqual(m.find_all("ushers his hers"), first)

    def test_compare_count_reset_and_grow(self):
        m = build_matcher()
        m.reset_compare_count()
        self.assertEqual(m.compare_count(), 0)
        m.find_all("ushers")
        after = m.compare_count()
        self.assertGreater(after, 0)
        m.reset_compare_count()
        self.assertEqual(m.compare_count(), 0)
        m.find_all("ushers")
        self.assertEqual(m.compare_count(), after)

    def test_two_matchers_do_not_share_state(self):
        a = build_matcher()
        b = build_matcher()
        a.find_all("ushers")
        self.assertEqual(b.compare_count(), 0)


if __name__ == "__main__":
    unittest.main()
