"""改造前行为的锁定测试：枚举子序列的朴素比对。"""

import unittest

from lcsalign.sequence import (
    EmptySequenceError,
    SequenceError,
    lcs_length,
    lcs_sequence,
    summary,
)


class TestLcsLength(unittest.TestCase):
    def test_classic_example(self):
        self.assertEqual(lcs_length("ABCBDAB", "BDCABA"), 4)

    def test_identical(self):
        self.assertEqual(lcs_length("ABCDE", "ABCDE"), 5)

    def test_disjoint(self):
        self.assertEqual(lcs_length("ABC", "XYZ"), 0)

    def test_one_is_subsequence(self):
        self.assertEqual(lcs_length("AC", "ABCDEF"), 2)

    def test_single_shared_element(self):
        self.assertEqual(lcs_length("AB", "BA"), 1)

    def test_repeated_elements(self):
        self.assertEqual(lcs_length("AAAA", "AA"), 2)

    def test_empty_raises(self):
        with self.assertRaises(EmptySequenceError):
            lcs_length("", "ABC")
        with self.assertRaises(EmptySequenceError):
            lcs_length("ABC", "")
        with self.assertRaises(SequenceError):
            lcs_length("", "ABC")


class TestLcsSequence(unittest.TestCase):
    def test_returns_an_elements_list(self):
        seq = lcs_sequence("ABCBDAB", "BDCABA")
        self.assertEqual(len(seq), 4)
        self.assertTrue(set(seq) <= {"A", "B", "C", "D"})

    def test_identical_returns_copy(self):
        seq = lcs_sequence("ABCDE", "ABCDE")
        self.assertEqual(seq, list("ABCDE"))

    def test_tie_prefers_leftmost_index_tuple(self):
        # AC 与 AB 都是长度 2 的公共子序列，AB 在 a 里的下标元组 (0,1) 更靠前。
        self.assertEqual(lcs_sequence("ABC", "ACB"), ["A", "B"])

    def test_tie_uses_first_sequence_positions(self):
        # AC 与 AD 并列，AC 在 a 里的下标元组 (0,2) 小于 AD 的 (0,3)。
        self.assertEqual(lcs_sequence("ABCD", "ADC"), ["A", "C"])

    def test_disjoint_returns_empty_list(self):
        self.assertEqual(lcs_sequence("ABC", "XYZ"), [])

    def test_repeated_elements(self):
        self.assertEqual(lcs_sequence("AAAA", "AA"), ["A", "A"])

    def test_empty_raises(self):
        with self.assertRaises(EmptySequenceError):
            lcs_sequence("", "ABC")


class TestDeterminism(unittest.TestCase):
    def test_repeat_is_stable(self):
        first = summary("ABCBDAB", "BDCABA")
        second = summary("ABCBDAB", "BDCABA")
        self.assertEqual(first, second)

    def test_summary_shape(self):
        got = summary("AGGTAB", "GXTXAYB")
        self.assertEqual(got["length"], 4)
        self.assertEqual(len(got["sequence"]), 4)


if __name__ == "__main__":
    unittest.main()
