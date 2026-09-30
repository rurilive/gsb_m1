"""SortedBag 现有行为的锁定基线。

这份测试锁住改造前的朴素排序数组语义，跳表改造之后必须一字不改且仍然全绿。
"""

import unittest

from skipx.sortedbag import (
    EmptyError,
    IndexError_,
    NotFoundError,
    SkipxError,
    SortedBag,
)


class TestBasics(unittest.TestCase):
    def test_empty(self):
        b = SortedBag()
        self.assertEqual(len(b), 0)
        self.assertTrue(b.is_empty())
        self.assertEqual(b.items(), [])

    def test_from_values_sorted(self):
        b = SortedBag([3, 1, 2, 1])
        self.assertEqual(b.items(), [1, 1, 2, 3])
        self.assertFalse(b.is_empty())

    def test_insert_keeps_sorted_and_duplicates(self):
        b = SortedBag()
        for v in (5, 1, 5, 3, 1):
            b.insert(v)
        self.assertEqual(b.items(), [1, 1, 3, 5, 5])
        self.assertEqual(len(b), 5)

    def test_contains(self):
        b = SortedBag([2, 4, 6])
        self.assertIn(4, b)
        self.assertNotIn(5, b)
        self.assertTrue(b.find(2))
        self.assertFalse(b.find(3))


class TestDelete(unittest.TestCase):
    def test_discard_present_and_missing(self):
        b = SortedBag([1, 1, 2])
        self.assertTrue(b.discard(1))
        self.assertEqual(b.items(), [1, 2])
        self.assertFalse(b.discard(9))
        self.assertEqual(len(b), 2)

    def test_remove_present_and_missing(self):
        b = SortedBag([1, 2, 3])
        b.remove(2)
        self.assertEqual(b.items(), [1, 3])
        with self.assertRaises(NotFoundError):
            b.remove(9)

    def test_pop_at(self):
        b = SortedBag([10, 20, 30])
        self.assertEqual(b.pop_at(1), 20)
        self.assertEqual(b.items(), [10, 30])

    def test_pop_at_out_of_range(self):
        b = SortedBag([1])
        with self.assertRaises(IndexError_):
            b.pop_at(1)
        with self.assertRaises(IndexError_):
            b.pop_at(-1)


class TestQuery(unittest.TestCase):
    def test_at(self):
        b = SortedBag([7, 3, 5])
        self.assertEqual(b.at(0), 3)
        self.assertEqual(b.at(2), 7)
        with self.assertRaises(IndexError_):
            b.at(3)

    def test_at_bad_type(self):
        b = SortedBag([1])
        with self.assertRaises(TypeError):
            b.at("0")

    def test_rank_counts_strictly_smaller(self):
        b = SortedBag([1, 2, 2, 4])
        self.assertEqual(b.rank(2), 1)
        self.assertEqual(b.rank(3), 3)
        self.assertEqual(b.rank(0), 0)
        self.assertEqual(b.rank(5), 4)

    def test_predecessor_successor(self):
        b = SortedBag([1, 2, 2, 4])
        self.assertEqual(b.predecessor(3), 2)
        self.assertEqual(b.successor(2), 4)
        self.assertEqual(b.successor(0), 1)

    def test_predecessor_successor_missing(self):
        b = SortedBag([1, 2])
        with self.assertRaises(NotFoundError):
            b.predecessor(1)
        with self.assertRaises(NotFoundError):
            b.successor(2)

    def test_range_scan_half_open(self):
        b = SortedBag([1, 2, 3, 4, 5])
        self.assertEqual(b.range_scan(2, 5), [2, 3, 4])
        self.assertEqual(b.range_scan(0, 9), [1, 2, 3, 4, 5])
        self.assertEqual(b.range_scan(5, 5), [])
        self.assertEqual(b.range_scan(4, 2), [])

    def test_probe_count(self):
        b = SortedBag([1, 3, 5, 7])
        self.assertEqual(b.probe_count(1), 1)
        self.assertEqual(b.probe_count(5), 3)
        self.assertEqual(b.probe_count(6), 4)
        self.assertEqual(b.probe_count(9), 4)


class TestBoundary(unittest.TestCase):
    def test_single_element(self):
        b = SortedBag([42])
        self.assertEqual(b.at(0), 42)
        self.assertEqual(b.rank(42), 0)
        self.assertEqual(b.range_scan(42, 43), [42])

    def test_all_equal(self):
        b = SortedBag([9, 9, 9])
        self.assertEqual(b.rank(9), 0)
        self.assertEqual(b.range_scan(9, 10), [9, 9, 9])
        self.assertTrue(b.discard(9))
        self.assertEqual(b.items(), [9, 9])

    def test_empty_operations_fail_fast(self):
        b = SortedBag()
        with self.assertRaises(NotFoundError):
            b.predecessor(1)
        with self.assertRaises(IndexError_):
            b.at(0)

    def test_errors_share_base(self):
        self.assertTrue(issubclass(NotFoundError, SkipxError))
        self.assertTrue(issubclass(IndexError_, SkipxError))
        self.assertTrue(issubclass(EmptyError, SkipxError))


if __name__ == "__main__":
    unittest.main()
