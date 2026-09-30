"""Catalanx 现有行为的锁定测试（改造前基线，不许改）。"""

import unittest

from catalanx.core import (
    Catalanx,
    CatalanxError,
    InvalidBracketError,
    OutOfRangeError,
    TypeMismatchError,
)


class TestCatalanRecursive(unittest.TestCase):
    def setUp(self):
        self.c = Catalanx()

    def test_small_values(self):
        self.assertEqual(self.c.catalan_recursive(0), 1)

    def test_one(self):
        self.assertEqual(self.c.catalan_recursive(1), 1)

    def test_two(self):
        self.assertEqual(self.c.catalan_recursive(2), 2)

    def test_five(self):
        self.assertEqual(self.c.catalan_recursive(5), 42)

    def test_eight(self):
        self.assertEqual(self.c.catalan_recursive(8), 1430)

    def test_negative(self):
        with self.assertRaises(OutOfRangeError):
            self.c.catalan_recursive(-1)

    def test_non_integer(self):
        with self.assertRaises(TypeMismatchError):
            self.c.catalan_recursive(2.0)

    def test_bool_rejected(self):
        with self.assertRaises(TypeMismatchError):
            self.c.catalan_recursive(True)

    def test_counters_are_non_negative(self):
        self.c.catalan_recursive(6)
        self.assertGreaterEqual(self.c.recursion_steps, 0)
        self.assertGreaterEqual(self.c.recurrence_visits, 0)


class TestIsValid(unittest.TestCase):
    def setUp(self):
        self.c = Catalanx()

    def test_empty_is_valid(self):
        self.assertTrue(self.c.is_valid(""))

    def test_simple_valid(self):
        self.assertTrue(self.c.is_valid("()()"))

    def test_nested_valid(self):
        self.assertTrue(self.c.is_valid("(())"))

    def test_unbalanced_closing(self):
        self.assertFalse(self.c.is_valid("())("))

    def test_extra_open(self):
        self.assertFalse(self.c.is_valid("(()"))

    def test_illegal_char(self):
        with self.assertRaises(InvalidBracketError):
            self.c.is_valid("(a)")

    def test_not_a_string(self):
        with self.assertRaises(TypeMismatchError):
            self.c.is_valid(12)


class TestValidPrefixCount(unittest.TestCase):
    def setUp(self):
        self.c = Catalanx()

    def test_empty(self):
        self.assertEqual(self.c.valid_prefix_count(""), 0)

    def test_pair(self):
        self.assertEqual(self.c.valid_prefix_count("()"), 1)

    def test_four(self):
        self.assertEqual(self.c.valid_prefix_count("(())"), 1)

    def test_two_pairs(self):
        self.assertEqual(self.c.valid_prefix_count("()()"), 2)

    def test_illegal_char(self):
        with self.assertRaises(InvalidBracketError):
            self.c.valid_prefix_count("(])")


class TestEnumerateAll(unittest.TestCase):
    def setUp(self):
        self.c = Catalanx()

    def test_zero(self):
        self.assertEqual(self.c.enumerate_all(0), [""])

    def test_one(self):
        self.assertEqual(self.c.enumerate_all(1), ["()"])

    def test_two(self):
        self.assertEqual(self.c.enumerate_all(2), ["()()", "(())"])

    def test_three_count(self):
        self.assertEqual(len(self.c.enumerate_all(3)), 5)

    def test_full_enumeration_count(self):
        self.c.enumerate_all(2)
        self.assertEqual(self.c.full_enumeration_count, 16)

    def test_full_enumeration_count_zero(self):
        self.c.enumerate_all(0)
        self.assertEqual(self.c.full_enumeration_count, 1)

    def test_negative(self):
        with self.assertRaises(OutOfRangeError):
            self.c.enumerate_all(-1)


class TestCountSequences(unittest.TestCase):
    def setUp(self):
        self.c = Catalanx()

    def test_five(self):
        self.assertEqual(self.c.count_sequences(3), 5)

    def test_six(self):
        self.assertEqual(self.c.count_sequences(6), 132)


class TestCountMonotonePaths(unittest.TestCase):
    def setUp(self):
        self.c = Catalanx()

    def test_zero(self):
        self.assertEqual(self.c.count_monotone_paths(0), 1)

    def test_two(self):
        self.assertEqual(self.c.count_monotone_paths(2), 2)

    def test_four(self):
        self.assertEqual(self.c.count_monotone_paths(4), 14)


class TestListAndRank(unittest.TestCase):
    def setUp(self):
        self.c = Catalanx()

    def test_first(self):
        self.assertEqual(self.c.list_sequence(2, 0), "(())")

    def test_last(self):
        self.assertEqual(self.c.list_sequence(2, 1), "()()")

    def test_out_of_range(self):
        with self.assertRaises(OutOfRangeError):
            self.c.list_sequence(2, 2)

    def test_negative_index(self):
        with self.assertRaises(OutOfRangeError):
            self.c.list_sequence(2, -1)

    def test_non_integer_index(self):
        with self.assertRaises(TypeMismatchError):
            self.c.list_sequence(2, 1.5)

    def test_rank_first(self):
        self.assertEqual(self.c.rank_sequence("(())"), 0)

    def test_rank_last(self):
        self.assertEqual(self.c.rank_sequence("()()"), 1)

    def test_rank_illegal(self):
        with self.assertRaises(InvalidBracketError):
            self.c.rank_sequence("())(")

    def test_rank_illegal_char(self):
        with self.assertRaises(InvalidBracketError):
            self.c.rank_sequence("(a)")

    def test_round_trip(self):
        for k in range(5):
            seq = self.c.list_sequence(3, k)
            self.assertEqual(self.c.rank_sequence(seq), k)


class TestErrorsShareOneRoot(unittest.TestCase):
    def test_subclasses(self):
        self.assertTrue(issubclass(TypeMismatchError, CatalanxError))
        self.assertTrue(issubclass(InvalidBracketError, CatalanxError))
        self.assertTrue(issubclass(OutOfRangeError, CatalanxError))


class TestDeterminism(unittest.TestCase):
    def test_repeated_calls_agree(self):
        c = Catalanx()
        first = c.catalan_recursive(5)
        second = c.catalan_recursive(5)
        self.assertEqual(first, second)

    def test_two_instances_agree(self):
        self.assertEqual(
            Catalanx().count_sequences(3),
            Catalanx().count_sequences(3),
        )

    def test_repeated_enumeration_agrees(self):
        c = Catalanx()
        self.assertEqual(c.enumerate_all(3), c.enumerate_all(3))


if __name__ == "__main__":
    unittest.main()
