"""NimGar 现有朴素行为的锁定测试。

这些用例锁住改造前基线的对外事实，全部通过后才算没有破坏现状。新行为另开
测试文件，本文件一个字都不许改。
"""

import unittest

from nimgar.core import (
    Erro,
    NimGar,
    ParamErro,
    RuleErro,
    StateErro,
)


def sub_one(state):
    """每次只取一颗的走法函数，供格林数使用。"""
    return [state - 1] if state >= 1 else []


def take_one_two(state):
    """每次取一至两颗的走法函数，供格林数使用。"""
    return [s for s in (state - 1, state - 2) if s >= 0]


def take_one_three(state):
    """每次取一或三颗的走法函数，供格林数使用。"""
    return [s for s in (state - 1, state - 3) if s >= 0]


class TestSingleHeap(unittest.TestCase):
    def setUp(self):
        self.g = NimGar()

    def test_one_at_a_time_parity(self):
        for n in range(0, 12):
            self.assertEqual(self.g.single_win(n, max_take=1), n % 2 == 1)

    def test_up_to_three_modulo_four(self):
        for n in range(0, 12):
            self.assertEqual(self.g.single_win(n, max_take=3), n % 4 != 0)

    def test_takes_list_one_two(self):
        for n in range(0, 12):
            self.assertEqual(self.g.single_win(n, takes=(1, 2)), n % 3 != 0)

    def test_empty_heap_is_loss(self):
        self.assertFalse(self.g.single_win(0, max_take=5))

    def test_single_stone_permissive_rule(self):
        self.assertTrue(self.g.single_win(1, max_take=5))

    def test_min_takes_one_at_a_time(self):
        self.assertEqual(self.g.single_min_takes(3, max_take=1), 2)
        self.assertEqual(self.g.single_min_takes(5, max_take=1), 3)

    def test_min_takes_up_to_three(self):
        self.assertEqual(self.g.single_min_takes(1, max_take=3), 1)
        self.assertEqual(self.g.single_min_takes(2, max_take=3), 1)
        self.assertEqual(self.g.single_min_takes(3, max_take=3), 1)
        self.assertEqual(self.g.single_min_takes(5, max_take=3), 2)
        self.assertEqual(self.g.single_min_takes(7, max_take=3), 2)

    def test_min_takes_none_when_losing(self):
        self.assertIsNone(self.g.single_min_takes(0, max_take=3))
        self.assertIsNone(self.g.single_min_takes(4, max_take=3))
        self.assertIsNone(self.g.single_min_takes(4, max_take=1))

    def test_min_takes_with_takes_list(self):
        self.assertEqual(self.g.single_min_takes(4, takes=(1, 2)), 2)

    def test_negative_size_rejected(self):
        with self.assertRaises(ParamErro):
            self.g.single_win(-1)


class TestMultiHeap(unittest.TestCase):
    def setUp(self):
        self.g = NimGar()

    def test_empty_xor_is_zero(self):
        self.assertEqual(self.g.multi_xor([]), 0)

    def test_all_zero_xor_is_zero(self):
        self.assertEqual(self.g.multi_xor([0, 0, 0]), 0)

    def test_single_heap_xor_is_size(self):
        self.assertEqual(self.g.multi_xor([7]), 7)

    def test_equal_pairs_cancel(self):
        self.assertEqual(self.g.multi_xor([2, 2]), 0)
        self.assertEqual(self.g.multi_xor([4, 4, 4, 4]), 0)

    def test_known_xor(self):
        self.assertEqual(self.g.multi_xor([3, 4, 5]), 2)

    def test_large_heap_count(self):
        heaps = list(range(1, 40))
        total = 0
        for h in heaps:
            total ^= h
        self.assertEqual(self.g.multi_xor(heaps), total)

    def test_winning_move_zeroes_xor(self):
        heaps = [3, 4, 5]
        move = self.g.multi_winning_move(heaps)
        self.assertIsNotNone(move)
        index, count = move
        rest = list(heaps)
        rest[index] -= count
        self.assertEqual(self.g.multi_xor(rest), 0)

    def test_winning_move_fixed_order(self):
        self.assertEqual(self.g.multi_winning_move([3, 4, 5]), (0, 2))
        self.assertEqual(self.g.multi_winning_move([1]), (0, 1))

    def test_no_winning_move_when_zero(self):
        self.assertIsNone(self.g.multi_winning_move([2, 2]))
        self.assertIsNone(self.g.multi_winning_move([]))

    def test_bad_heap_rejected(self):
        with self.assertRaises(ParamErro):
            self.g.multi_xor([1, -2])


class TestGrundy(unittest.TestCase):
    def setUp(self):
        self.g = NimGar()

    def test_terminal_grundy_zero(self):
        self.assertEqual(self.g.grundy(0, sub_one), 0)

    def test_sub_one_alternates(self):
        for n in range(0, 9):
            self.assertEqual(self.g.grundy(n, sub_one), n % 2)

    def test_take_one_two_modulo_three(self):
        for n in range(0, 10):
            self.assertEqual(self.g.grundy(n, take_one_two), n % 3)

    def test_take_one_three_parity(self):
        for n in range(0, 10):
            self.assertEqual(self.g.grundy(n, take_one_three), n % 2)

    def test_bad_state_rejected(self):
        with self.assertRaises(ParamErro):
            self.g.grundy(-1, sub_one)


class TestSumGames(unittest.TestCase):
    def setUp(self):
        self.g = NimGar()

    def test_empty_sum_is_loss(self):
        self.assertFalse(self.g.sum_win([], []))

    def test_matches_xor_on_one_game(self):
        for n in range(0, 9):
            expected = (self.g.grundy(n, take_one_two) != 0)
            self.assertEqual(self.g.sum_win([n], [take_one_two]), expected)

    def test_matches_xor_on_two_games(self):
        for a in range(0, 6):
            for b in range(0, 6):
                expected = (
                    self.g.grundy(a, take_one_two) ^ self.g.grundy(b, take_one_two)
                ) != 0
                self.assertEqual(
                    self.g.sum_win([a, b], [take_one_two, take_one_two]), expected
                )

    def test_three_copies_cancel(self):
        self.assertFalse(self.g.sum_win([1, 1], [take_one_two, take_one_two]))

    def test_mismatched_lengths_rejected(self):
        with self.assertRaises(StateErro):
            self.g.sum_win([1, 2], [take_one_two])


class TestWythoff(unittest.TestCase):
    def setUp(self):
        self.g = NimGar()

    def test_cold_pairs_are_losses(self):
        for a, b in ((0, 0), (1, 2), (3, 5), (4, 7), (6, 10)):
            self.assertFalse(self.g.wythoff_win(a, b))
            self.assertFalse(self.g.wythoff_win(b, a))

    def test_hot_pairs_are_wins(self):
        for a, b in ((1, 1), (2, 2), (2, 3), (5, 5), (0, 1), (0, 3)):
            self.assertTrue(self.g.wythoff_win(a, b))

    def test_cold_pair_has_no_move(self):
        self.assertIsNone(self.g.wythoff_move(1, 2))
        self.assertIsNone(self.g.wythoff_move(0, 0))

    def test_move_lands_on_cold_pair(self):
        a, b = 3, 3
        move = self.g.wythoff_move(a, b)
        self.assertIsNotNone(move)
        side, count = move
        left, right = a, b
        if side == 0:
            left -= count
        elif side == 1:
            right -= count
        else:
            left -= count
            right -= count
        self.assertFalse(self.g.wythoff_win(left, right))

    def test_negative_rejected(self):
        with self.assertRaises(ParamErro):
            self.g.wythoff_win(-1, 0)


class TestFibonacci(unittest.TestCase):
    def setUp(self):
        self.g = NimGar()

    def test_cold_sizes_are_losses(self):
        for n in (0, 1, 2, 3, 5, 8, 13):
            self.assertFalse(self.g.fib_win(n))

    def test_hot_sizes_are_wins(self):
        for n in (4, 6, 7, 9, 10, 11, 12):
            self.assertTrue(self.g.fib_win(n))

    def test_cold_size_has_no_move(self):
        self.assertIsNone(self.g.fib_move(3))
        self.assertIsNone(self.g.fib_move(5))
        self.assertIsNone(self.g.fib_move(1))

    def test_first_move_leaves_losing_position(self):
        n = 4
        take = self.g.fib_move(n)
        self.assertEqual(take, 1)
        self.assertFalse(self.g._rec_fib(n - take, take, False))

    def test_negative_rejected(self):
        with self.assertRaises(ParamErro):
            self.g.fib_win(-1)


class TestErrorsShareOneRoot(unittest.TestCase):
    def test_subclasses(self):
        self.assertTrue(issubclass(ParamErro, Erro))
        self.assertTrue(issubclass(RuleErro, Erro))
        self.assertTrue(issubclass(StateErro, Erro))

    def test_empty_takes_list_rejected(self):
        with self.assertRaises(RuleErro):
            NimGar().single_win(5, takes=[])

    def test_non_positive_take_rejected(self):
        with self.assertRaises(RuleErro):
            NimGar().single_win(5, takes=(0, 1))


class TestDeterminism(unittest.TestCase):
    def test_repeat_runs_agree(self):
        g1 = NimGar()
        g2 = NimGar()
        self.assertEqual(g1.single_win(9, max_take=3), g2.single_win(9, max_take=3))
        self.assertEqual(g1.multi_xor([3, 4, 5]), g2.multi_xor([3, 4, 5]))
        self.assertEqual(g1.grundy(7, take_one_two), g2.grundy(7, take_one_two))
        self.assertEqual(g1.wythoff_win(4, 7), g2.wythoff_win(4, 7))
        self.assertEqual(g1.fib_win(10), g2.fib_win(10))


if __name__ == "__main__":
    unittest.main()
