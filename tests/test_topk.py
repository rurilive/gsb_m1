"""Baseline tests for rankly.topk.SortTopK.

These tests lock down the current naive behaviour.  They must stay green and
must not be modified by later feature work.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rankly import SortTopK


class SortTopKTest(unittest.TestCase):
    def test_top_k_descending(self):
        tool = SortTopK([3, 1, 4, 1, 5, 9, 2, 6], k=3)
        self.assertEqual(tool.top(), [9, 6, 5])

    def test_k_larger_than_input_returns_all(self):
        tool = SortTopK([2, 7, 1], k=10)
        self.assertEqual(tool.top(), [7, 2, 1])

    def test_k_zero_returns_empty(self):
        tool = SortTopK([2, 7, 1], k=0)
        self.assertEqual(tool.top(), [])

    def test_size_reflects_full_input(self):
        tool = SortTopK([5, 5, 5, 5], k=2)
        self.assertEqual(tool.size(), 4)
        self.assertEqual(tool.top(), [5, 5])

    def test_negative_k_rejected(self):
        with self.assertRaises(ValueError):
            SortTopK([1, 2, 3], k=-1)

    def test_non_int_k_rejected(self):
        with self.assertRaises(TypeError):
            SortTopK([1, 2, 3], k=2.0)

    def test_accepts_generator(self):
        tool = SortTopK((x * x for x in range(5)), k=2)
        self.assertEqual(tool.top(), [16, 9])


if __name__ == "__main__":
    unittest.main()
