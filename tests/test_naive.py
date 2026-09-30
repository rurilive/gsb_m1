"""Josephus 现有朴素模拟行为的锁定测试。"""

import unittest

from joseph import (
    InvalidCountError,
    Josephus,
    JosephusError,
    PositionError,
    StartConventionError,
)


class TestEliminationOrder(unittest.TestCase):
    def test_basic_five_two(self):
        self.assertEqual(Josephus(5, 2).order(), [1, 3, 0, 4, 2])

    def test_seven_three(self):
        self.assertEqual(Josephus(7, 3).order(), [2, 5, 1, 6, 4, 0, 3])

    def test_six_four(self):
        self.assertEqual(Josephus(6, 4).order(), [3, 1, 0, 2, 5, 4])

    def test_one_based_convention(self):
        self.assertEqual(Josephus(5, 2, convention="one").order(), [2, 4, 1, 5, 3])

    def test_k_one_kills_in_order(self):
        self.assertEqual(Josephus(4, 1).order(), [0, 1, 2, 3])

    def test_k_greater_than_n_wraps(self):
        self.assertEqual(Josephus(3, 7).order(), [0, 1, 2])

    def test_k_equals_n(self):
        self.assertEqual(Josephus(3, 3).order(), [2, 0, 1])

    def test_single_person(self):
        self.assertEqual(Josephus(1, 1).order(), [0])
        self.assertEqual(Josephus(1, 5).order(), [0])

    def test_no_people(self):
        self.assertEqual(Josephus(0, 2).order(), [])

    def test_start_offsets_first_count(self):
        self.assertEqual(Josephus(5, 2, start=3).order(), [4, 1, 3, 2, 0])


class TestSurvivor(unittest.TestCase):
    def test_survivor_basic(self):
        self.assertEqual(Josephus(5, 2).survivor(), 2)

    def test_survivor_seven_three(self):
        self.assertEqual(Josephus(7, 3).survivor(), 3)

    def test_survivor_single(self):
        self.assertEqual(Josephus(1, 1).survivor(), 0)

    def test_survivor_equals_last_of_order(self):
        sim = Josephus(9, 4)
        self.assertEqual(sim.survivor(), sim.order()[-1])

    def test_no_people_has_no_survivor(self):
        with self.assertRaises(InvalidCountError):
            Josephus(0, 2).survivor()


class TestRankToBeRemoved(unittest.TestCase):
    def test_first(self):
        self.assertEqual(Josephus(5, 2).rank_to_be_removed(1), 1)

    def test_middle(self):
        self.assertEqual(Josephus(5, 2).rank_to_be_removed(3), 0)

    def test_last(self):
        self.assertEqual(Josephus(5, 2).rank_to_be_removed(5), 2)

    def test_out_of_range_high(self):
        with self.assertRaises(PositionError):
            Josephus(5, 2).rank_to_be_removed(6)

    def test_out_of_range_zero(self):
        with self.assertRaises(PositionError):
            Josephus(5, 2).rank_to_be_removed(0)

    def test_non_integer(self):
        with self.assertRaises(InvalidCountError):
            Josephus(5, 2).rank_to_be_removed(1.5)


class TestEliminationIndex(unittest.TestCase):
    def test_index_of_value(self):
        self.assertEqual(Josephus(5, 2).elimination_index(3), 2)

    def test_index_of_last(self):
        self.assertEqual(Josephus(5, 2).elimination_index(2), 5)

    def test_value_not_eliminated(self):
        with self.assertRaises(PositionError):
            Josephus(5, 2).elimination_index(99)


class TestValidation(unittest.TestCase):
    def test_negative_n(self):
        with self.assertRaises(InvalidCountError):
            Josephus(-1, 2)

    def test_zero_k(self):
        with self.assertRaises(InvalidCountError):
            Josephus(5, 0)

    def test_none_integer(self):
        with self.assertRaises(InvalidCountError):
            Josephus(5.0, 2)

    def test_k_float(self):
        with self.assertRaises(InvalidCountError):
            Josephus(5, 2.5)

    def test_bad_convention(self):
        with self.assertRaises(StartConventionError):
            Josephus(5, 2, convention="two")

    def test_exceptions_share_base(self):
        for exc in (InvalidCountError, PositionError, StartConventionError):
            self.assertTrue(issubclass(exc, JosephusError))


class TestDeterminismAndScale(unittest.TestCase):
    def test_replay_matches(self):
        sim = Josephus(11, 3)
        self.assertEqual(sim.replay_order(), sim.order())

    def test_two_instances_agree(self):
        self.assertEqual(Josephus(11, 3).order(), Josephus(11, 3).order())

    def test_move_count_positive(self):
        self.assertGreater(Josephus(6, 2).move_count(), 0)

    def test_move_count_grows_quadratically(self):
        small = Josephus(10, 2).move_count()
        big = Josephus(40, 2).move_count()
        self.assertGreater(big, small * 4)

    def test_move_snapshot_length(self):
        sim = Josephus(5, 2)
        self.assertEqual(len(sim.move_counts_per_step()), 5)

    def test_move_snapshot_monotonic(self):
        snapshot = Josephus(6, 2).move_counts_per_step()
        self.assertEqual(snapshot, sorted(snapshot))


class TestBatchFacts(unittest.TestCase):
    def test_batch(self):
        from joseph.core import BatchFacts

        facts = BatchFacts([(5, 2), (7, 3)]).run()
        self.assertEqual(facts[0]["survivor"], 2)
        self.assertEqual(facts[1]["order"], [2, 5, 1, 6, 4, 0, 3])
        self.assertEqual(facts[0]["n"], 5)
        self.assertGreater(facts[1]["moves"], 0)


if __name__ == "__main__":
    unittest.main()
