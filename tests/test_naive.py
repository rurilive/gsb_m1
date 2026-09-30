"""votehal 现有朴素行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from votehal.naive import (
    Erro,
    VoteError,
    VoteTools,
    count_value,
    frequent_values,
    has_majority,
    majority_count,
    majority_value,
    naive_counts,
    top_frequent,
    two_pass_majority,
    visit_count,
)


class TestCounts(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(naive_counts([1, 1, 2]), {1: 2, 2: 1})

    def test_empty(self):
        self.assertEqual(naive_counts([]), {})

    def test_negatives(self):
        self.assertEqual(naive_counts([-1, -1, -2]), {-1: 2, -2: 1})

    def test_all_equal(self):
        self.assertEqual(naive_counts([7, 7, 7]), {7: 3})

    def test_all_distinct(self):
        self.assertEqual(naive_counts([1, 2, 3]), {1: 1, 2: 1, 3: 1})

    def test_count_value(self):
        self.assertEqual(count_value([3, 3, 4], 3), 2)
        self.assertEqual(count_value([3, 3, 4], 9), 0)

    def test_count_value_empty(self):
        self.assertEqual(count_value([], 1), 0)

    def test_visit_count(self):
        self.assertEqual(visit_count([1, 1, 2]), 2)
        self.assertEqual(visit_count([]), 0)
        self.assertEqual(visit_count([5, 6, 7]), 3)

    def test_non_list_rejected(self):
        with self.assertRaises(VoteError):
            naive_counts("abc")

    def test_vote_error_is_erro(self):
        self.assertTrue(issubclass(VoteError, Erro))


class TestMajority(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(majority_value([1, 1, 2]), 1)
        self.assertEqual(majority_count([1, 1, 2]), 2)
        self.assertTrue(has_majority([1, 1, 2]))

    def test_absent(self):
        self.assertIsNone(majority_value([1, 2, 3]))
        self.assertEqual(majority_count([1, 2, 3]), 0)
        self.assertFalse(has_majority([1, 2, 3]))

    def test_exactly_half(self):
        self.assertIsNone(majority_value([1, 1, 2, 2]))
        self.assertFalse(has_majority([1, 1, 2, 2]))

    def test_all_equal(self):
        self.assertEqual(majority_value([9, 9, 9, 9]), 9)
        self.assertEqual(majority_count([9, 9, 9, 9]), 4)

    def test_empty(self):
        self.assertIsNone(majority_value([]))
        self.assertEqual(majority_count([]), 0)
        self.assertFalse(has_majority([]))

    def test_single(self):
        self.assertEqual(majority_value([4]), 4)
        self.assertEqual(majority_count([4]), 1)

    def test_majority_at_ends(self):
        self.assertEqual(majority_value([2, 5, 5, 5, 2]), 5)

    def test_negative_majority(self):
        self.assertEqual(majority_value([-7, -7, 1]), -7)

    def test_reuses_counts_argument(self):
        counts = naive_counts([1, 1, 1, 2])
        self.assertEqual(majority_value([1, 1, 1, 2], counts), 1)
        self.assertEqual(majority_count([1, 1, 1, 2], counts), 3)


class TestFrequent(unittest.TestCase):
    def test_one_of_two(self):
        self.assertEqual(frequent_values([1, 1, 1, 2], 2), [1])

    def test_one_of_three(self):
        self.assertEqual(frequent_values([1, 1, 1, 2, 2, 3], 3), [1])

    def test_multi_sorted(self):
        self.assertEqual(frequent_values([1, 1, 1, 2, 2, 3, 3, 3], 3), [1, 3])

    def test_none_over_threshold(self):
        self.assertEqual(frequent_values([1, 1, 2, 2], 2), [])

    def test_k_equal_one(self):
        self.assertEqual(frequent_values([1, 2, 3], 1), [])

    def test_k_bigger_than_distinct(self):
        self.assertEqual(frequent_values([1, 2, 3], 10), [])

    def test_empty(self):
        self.assertEqual(frequent_values([], 2), [])

    def test_negatives_sorted(self):
        self.assertEqual(frequent_values([-3, -3, -3, -1, 0], 2), [-3])

    def test_reuses_counts_argument(self):
        counts = naive_counts([1, 1, 1, 2])
        self.assertEqual(frequent_values([1, 1, 1, 2], 2, counts), [1])

    def test_k_invalid(self):
        with self.assertRaises(VoteError):
            frequent_values([1], 0)

    def test_k_non_int(self):
        with self.assertRaises(VoteError):
            frequent_values([1], 2.5)


class TestTopFrequent(unittest.TestCase):
    def test_tie_by_value(self):
        self.assertEqual(top_frequent([1, 1, 2, 2, 3], 2), [(2, 1), (2, 2)])

    def test_limit(self):
        self.assertEqual(top_frequent([1, 1, 1, 2, 2, 3], 1), [(3, 1)])

    def test_zero(self):
        self.assertEqual(top_frequent([1, 1, 2], 0), [])

    def test_empty(self):
        self.assertEqual(top_frequent([], 3), [])

    def test_n_more_than_distinct(self):
        self.assertEqual(top_frequent([1, 1, 2], 5), [(2, 1), (1, 2)])

    def test_negatives_tie(self):
        self.assertEqual(top_frequent([-2, -2, 1, 1], 2), [(2, -2), (2, 1)])

    def test_negative_n_rejected(self):
        with self.assertRaises(VoteError):
            top_frequent([1], -1)


class TestTwoPass(unittest.TestCase):
    def test_present(self):
        self.assertEqual(two_pass_majority([1, 1, 2]), (1, 2, 4))

    def test_absent(self):
        self.assertEqual(two_pass_majority([1, 2, 3]), (None, 0, 6))

    def test_absent_exactly_half(self):
        self.assertEqual(two_pass_majority([1, 1, 2, 2]), (None, 0, 8))

    def test_empty(self):
        self.assertEqual(two_pass_majority([]), (None, 0, 0))

    def test_visit_linear(self):
        value, hit, visited = two_pass_majority([5, 5, 5, 6])
        self.assertEqual((value, hit), (5, 3))
        self.assertLessEqual(visited, 2 * 4 + 1)


class TestVoteTools(unittest.TestCase):
    def test_rescan_and_visit_counts(self):
        tools = VoteTools([1, 1, 2])
        tools.reset_rescan_count()
        self.assertEqual(tools.rescan_count(), 0)
        self.assertEqual(tools.visit_count(), 0)
        counts = tools.counts()
        self.assertEqual(counts, {1: 2, 2: 1})
        self.assertEqual(tools.rescan_count(), 2)
        self.assertEqual(tools.visit_count(), 6)

    def test_majority_tuple(self):
        tools = VoteTools([1, 1, 2])
        tools.reset_rescan_count()
        self.assertEqual(tools.majority(), (1, 2))
        self.assertGreater(tools.rescan_count(), 0)

    def test_top(self):
        tools = VoteTools([1, 1, 2, 2, 3])
        self.assertEqual(tools.top(2), [(2, 1), (2, 2)])

    def test_seq_accessor(self):
        self.assertEqual(VoteTools([1, 2]).seq(), [1, 2])

    def test_two_tools_do_not_share_state(self):
        a = VoteTools([1, 1, 2])
        b = VoteTools([1, 1, 2])
        a.counts()
        self.assertEqual(b.visit_count(), 0)

    def test_reset_clears_both(self):
        tools = VoteTools([1, 1, 2])
        tools.counts()
        tools.reset_rescan_count()
        self.assertEqual(tools.rescan_count(), 0)
        self.assertEqual(tools.visit_count(), 0)

    def test_non_list_rejected(self):
        with self.assertRaises(VoteError):
            VoteTools(None)


class TestDeterminism(unittest.TestCase):
    def test_repeated_run_same_result(self):
        seq = [1, 1, 2, 3, 3, 3]
        first = (naive_counts(seq), top_frequent(seq, 3), two_pass_majority(seq))
        for _ in range(3):
            self.assertEqual(
                (naive_counts(seq), top_frequent(seq, 3),
                 two_pass_majority(seq)),
                first,
            )


if __name__ == "__main__":
    unittest.main()
