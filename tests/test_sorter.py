"""NaiveSorter 现有行为的锁定测试。"""

import unittest

from sortlab.sorter import NaiveSorter


class TestNaiveSorter(unittest.TestCase):
    def setUp(self):
        self.sorter = NaiveSorter()

    def test_sorts_small_integers(self):
        self.assertEqual(self.sorter.sort([3, 1, 2]), [1, 2, 3])

    def test_sorts_negatives(self):
        self.assertEqual(self.sorter.sort([0, -5, 3, -1]), [-5, -1, 0, 3])

    def test_returns_new_list_and_keeps_input(self):
        values = [3, 1, 2]
        result = self.sorter.sort(values)
        self.assertEqual(result, [1, 2, 3])
        self.assertEqual(values, [3, 1, 2])
        self.assertIsNot(result, values)

    def test_empty_and_single(self):
        self.assertEqual(self.sorter.sort([]), [])
        self.assertEqual(self.sorter.sort([7]), [7])

    def test_already_sorted_and_reversed(self):
        self.assertEqual(self.sorter.sort([1, 2, 3, 4]), [1, 2, 3, 4])
        self.assertEqual(self.sorter.sort([4, 3, 2, 1]), [1, 2, 3, 4])

    def test_duplicates(self):
        self.assertEqual(self.sorter.sort([2, 2, 1, 1, 2]), [1, 1, 2, 2, 2])

    def test_sorted_alias(self):
        self.assertEqual(self.sorter.sorted([9, 0, 4]), [0, 4, 9])


if __name__ == "__main__":
    unittest.main()
