"""autolab 现有朴素模拟器行为的锁定测试。

这一组用例只锁住改造前就成立、改造后也必须继续成立的事实：给定一张
转移表，从初态出发逐字符推进，走完全程停在接受态就算接受，否则不
接受；中途缺少转移即判不中。这些用例现在全部通过，改造之后也必须
继续原样通过。
"""

import unittest

from autolab import NaiveDFA
from autolab.dfa import AutError


# 一个只接受含偶数个 a 的串的小自动机，字母表为 {a, b}。
EVEN_A = NaiveDFA(
    transitions={
        ("even", "a"): "odd",
        ("even", "b"): "even",
        ("odd", "a"): "even",
        ("odd", "b"): "odd",
    },
    start="even",
    accepts={"even"},
)


# 一个不接受任何串的小自动机。
EMPTY = NaiveDFA(
    transitions={
        ("q0", "a"): "q0",
        ("q0", "b"): "q0",
    },
    start="q0",
    accepts=set(),
)


class TestNaiveDFAConstruction(unittest.TestCase):
    def test_start_and_accepts_recorded(self):
        self.assertEqual(EVEN_A.start, "even")
        self.assertIn("even", EVEN_A.accepts)

    def test_accepts_is_frozen_set(self):
        self.assertIsInstance(EVEN_A.accepts, frozenset)


class TestNaiveDFARun(unittest.TestCase):
    def test_empty_string_stays_at_start(self):
        self.assertEqual(EVEN_A.run(""), "even")

    def test_run_follows_transitions(self):
        self.assertEqual(EVEN_A.run("a"), "odd")
        self.assertEqual(EVEN_A.run("aa"), "even")

    def test_run_returns_none_without_transition(self):
        dfa = NaiveDFA(transitions={("s0", "a"): "s1"}, start="s0", accepts={"s1"})
        self.assertIsNone(dfa.run("b"))
        self.assertIsNone(dfa.run("ab"))


class TestNaiveDFAAcceptance(unittest.TestCase):
    def test_even_number_of_a_accepted(self):
        for text in ["", "aa", "aaaa", "b", "abab", "aabb"]:
            self.assertTrue(EVEN_A.accepts_str(text), text)

    def test_odd_number_of_a_rejected(self):
        for text in ["a", "aaa", "ab", "ba", "bab"]:
            self.assertFalse(EVEN_A.accepts_str(text), text)

    def test_empty_language_rejects_everything(self):
        for text in ["", "a", "ab", "bb"]:
            self.assertFalse(EMPTY.accepts_str(text), text)

    def test_unknown_symbol_is_rejected(self):
        self.assertFalse(EVEN_A.accepts_str("c"))


class TestAutErrorBase(unittest.TestCase):
    def test_aut_error_is_exception(self):
        self.assertTrue(issubclass(AutError, Exception))


if __name__ == "__main__":
    unittest.main()
