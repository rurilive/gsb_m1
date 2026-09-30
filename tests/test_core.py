"""PermOrder 现有行为的锁定测试。"""

import unittest

from permorder.core import (
    OutOfRangeError,
    PermOrder,
    PermOrderError,
    TypeMismatchError,
    UnsortedBasisError,
)


class TestNextPermutation(unittest.TestCase):
    def setUp(self):
        self.p = PermOrder()

    def test_middle(self):
        self.assertEqual(self.p.next_permutation([1, 2, 3]), [1, 3, 2])

    def test_in_place_rewrites_list(self):
        items = [1, 2, 3]
        self.p.next_permutation(items)
        self.assertEqual(items, [1, 3, 2])

    def test_single_element_wraps_to_itself(self):
        self.assertEqual(self.p.next_permutation([5]), [5])

    def test_empty_wraps_to_itself(self):
        self.assertEqual(self.p.next_permutation([]), [])

    def test_last_wraps_to_first(self):
        self.assertEqual(self.p.next_permutation([3, 2, 1]), [1, 2, 3])

    def test_duplicates_next(self):
        self.assertEqual(self.p.next_permutation([1, 1, 2]), [1, 2, 1])

    def test_all_same_wraps_to_itself(self):
        self.assertEqual(self.p.next_permutation([2, 2, 2]), [2, 2, 2])

    def test_type_mismatch(self):
        with self.assertRaises(TypeMismatchError):
            self.p.next_permutation("abc")


class TestKthPermutation(unittest.TestCase):
    def setUp(self):
        self.p = PermOrder()

    def test_first(self):
        self.assertEqual(self.p.kth_permutation([1, 2, 3], 0), [1, 2, 3])

    def test_last(self):
        self.assertEqual(self.p.kth_permutation([1, 2, 3], 5), [3, 2, 1])

    def test_unsorted_input_uses_own_multiset(self):
        self.assertEqual(self.p.kth_permutation([3, 1, 2], 0), [1, 2, 3])

    def test_with_duplicates(self):
        self.assertEqual(self.p.kth_permutation([1, 1, 2], 1), [1, 2, 1])

    def test_out_of_range(self):
        with self.assertRaises(OutOfRangeError):
            self.p.kth_permutation([1, 2, 3], 6)

    def test_negative_index(self):
        with self.assertRaises(OutOfRangeError):
            self.p.kth_permutation([1, 2, 3], -1)

    def test_non_integer_index(self):
        with self.assertRaises(TypeMismatchError):
            self.p.kth_permutation([1, 2, 3], 1.5)


class TestRankAndUnrank(unittest.TestCase):
    def setUp(self):
        self.p = PermOrder()

    def test_rank_first(self):
        self.assertEqual(self.p.rank([1, 2, 3]), 0)

    def test_rank_last(self):
        self.assertEqual(self.p.rank([3, 2, 1]), 5)

    def test_rank_with_duplicates(self):
        self.assertEqual(self.p.rank([1, 2, 1]), 1)

    def test_unrank_round_trip(self):
        basis = [1, 2, 3]
        for k in range(6):
            perm = self.p.unrank(basis, k)
            self.assertEqual(self.p.rank(perm), k)

    def test_unrank_unsorted_basis(self):
        with self.assertRaises(UnsortedBasisError):
            self.p.unrank([3, 1, 2], 0)

    def test_unrank_out_of_range(self):
        with self.assertRaises(OutOfRangeError):
            self.p.unrank([1, 2, 3], 6)


class TestIsPermutation(unittest.TestCase):
    def setUp(self):
        self.p = PermOrder()

    def test_true(self):
        self.assertTrue(self.p.is_permutation([1, 2, 3], [3, 1, 2]))

    def test_false_different_length(self):
        self.assertFalse(self.p.is_permutation([1, 2], [1, 2, 3]))

    def test_false_different_values(self):
        self.assertFalse(self.p.is_permutation([1, 2, 3], [1, 2, 4]))

    def test_true_with_duplicates(self):
        self.assertTrue(self.p.is_permutation([1, 1, 2], [1, 2, 1]))

    def test_empty_pair(self):
        self.assertTrue(self.p.is_permutation([], []))

    def test_type_mismatch(self):
        with self.assertRaises(TypeMismatchError):
            self.p.is_permutation([1, 2], "12")


class TestErrorsShareOneRoot(unittest.TestCase):
    def test_subclasses(self):
        self.assertTrue(issubclass(TypeMismatchError, PermOrderError))
        self.assertTrue(issubclass(OutOfRangeError, PermOrderError))
        self.assertTrue(issubclass(UnsortedBasisError, PermOrderError))


class TestDeterminism(unittest.TestCase):
    def test_repeated_calls_agree(self):
        p = PermOrder()
        first = p.next_permutation([1, 2, 3])
        second = p.next_permutation([1, 2, 3])
        self.assertEqual(first, second)

    def test_two_instances_agree(self):
        self.assertEqual(
            PermOrder().kth_permutation([1, 2, 3], 3),
            PermOrder().kth_permutation([1, 2, 3], 3),
        )


if __name__ == "__main__":
    unittest.main()
