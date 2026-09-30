"""朴素异或集合的基线行为测试。

锁住改造前的现状: 插入、删除、异或极大极小、两数异或最大的答案口径,
以及异常基类与越界拒绝。本文件在改造后一字不许改, 且必须一直全绿。
"""

import unittest

from bittrie import (
    Erro,
    EmptyCollectionError,
    FlatXorMax,
    MissingElementError,
    NonNegativeIntError,
    TooFewElementsError,
)

SAMPLE = (3, 10, 5, 25, 2, 8)


class TestStructure(unittest.TestCase):
    def test_empty(self):
        s = FlatXorMax()
        self.assertEqual(len(s), 0)
        self.assertEqual(s.values(), [])
        self.assertEqual(s.bits, 30)

    def test_add_and_len_and_contains(self):
        s = FlatXorMax()
        for v in (3, 10, 5):
            s.add(v)
        self.assertEqual(len(s), 3)
        self.assertIn(3, s)
        self.assertIn(10, s)
        self.assertNotIn(7, s)

    def test_add_duplicates_kept_by_count(self):
        s = FlatXorMax()
        for _ in range(3):
            s.add(4)
        self.assertEqual(len(s), 3)
        self.assertEqual(s.values(), [4, 4, 4])

    def test_values_is_a_copy(self):
        s = FlatXorMax()
        s.add(1)
        got = s.values()
        got.append(2)
        self.assertEqual(len(s), 1)

    def test_custom_bits_limits_values(self):
        s = FlatXorMax(bits=4)
        self.assertEqual(s.bits, 4)
        s.add(15)
        with self.assertRaises(NonNegativeIntError):
            s.add(16)


class TestValidation(unittest.TestCase):
    def test_add_rejects_non_int(self):
        s = FlatXorMax()
        with self.assertRaises(NonNegativeIntError):
            s.add("9")
        with self.assertRaises(NonNegativeIntError):
            s.add(True)
        with self.assertRaises(NonNegativeIntError):
            s.add(-1)
        with self.assertRaises(NonNegativeIntError):
            s.add(1 << 30)

    def test_all_errors_share_base(self):
        for exc in (NonNegativeIntError, EmptyCollectionError,
                    MissingElementError, TooFewElementsError):
            self.assertTrue(issubclass(exc, Erro))
            self.assertTrue(issubclass(exc, Exception))


class TestRemove(unittest.TestCase):
    def test_remove_one_of_duplicates(self):
        s = FlatXorMax()
        s.add(6)
        s.add(6)
        s.remove(6)
        self.assertEqual(len(s), 1)
        self.assertIn(6, s)

    def test_remove_absent_raises(self):
        s = FlatXorMax()
        s.add(1)
        with self.assertRaises(MissingElementError):
            s.remove(99)

    def test_remove_to_empty(self):
        s = FlatXorMax()
        s.add(7)
        s.remove(7)
        self.assertEqual(len(s), 0)
        with self.assertRaises(EmptyCollectionError):
            s.query_max_xor(0)


class TestXorExtremes(unittest.TestCase):
    def setUp(self):
        self.s = FlatXorMax()
        for v in SAMPLE:
            self.s.add(v)

    def test_query_max_xor(self):
        self.assertEqual(self.s.query_max_xor(8), 25)
        self.assertEqual(self.s.query_max_xor(0), 25)

    def test_query_min_xor(self):
        self.assertEqual(self.s.query_min_xor(8), 8)
        self.assertEqual(self.s.query_min_xor(0), 2)

    def test_empty_raises(self):
        s = FlatXorMax()
        with self.assertRaises(EmptyCollectionError):
            s.query_max_xor(1)
        with self.assertRaises(EmptyCollectionError):
            s.query_min_xor(1)

    def test_single_element(self):
        s = FlatXorMax()
        s.add(9)
        self.assertEqual(s.query_max_xor(2), 9)
        self.assertEqual(s.query_min_xor(2), 9)


class TestXorPair(unittest.TestCase):
    def test_pair(self):
        s = FlatXorMax()
        for v in SAMPLE:
            s.add(v)
        self.assertEqual(s.max_pair_xor(), 28)

    def test_pair_needs_two(self):
        s = FlatXorMax()
        with self.assertRaises(TooFewElementsError):
            s.max_pair_xor()
        s.add(7)
        with self.assertRaises(TooFewElementsError):
            s.max_pair_xor()

    def test_pair_all_equal_is_zero(self):
        s = FlatXorMax()
        s.add(7)
        s.add(7)
        self.assertEqual(s.max_pair_xor(), 0)

    def test_pair_upper_bound_values(self):
        s = FlatXorMax()
        s.add(0)
        s.add((1 << 30) - 1)
        self.assertEqual(s.max_pair_xor(), (1 << 30) - 1)


if __name__ == "__main__":
    unittest.main()
