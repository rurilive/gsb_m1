"""hanoi.core 现有行为的锁定测试（基线，一字不改）。

基线实现递归生成完整移动序列，规模小的时候结果正确；这里只锁住在小规模
上能稳定复现的现状行为，测试不依赖任何模块级可变状态。
"""

import unittest

from hanoi.core import (
    HanoiError,
    InvalidMoveError,
    InvalidPegError,
    StepOutOfRangeError,
    generate_moves,
    hanoi4,
    is_valid_sequence,
    kth_move,
    min_moves_restricted,
    min_moves_to,
    move_count,
    step_moves,
)


class TestMoveCount(unittest.TestCase):
    def test_small(self):
        self.assertEqual(move_count(0), 0)
        self.assertEqual(move_count(1), 1)
        self.assertEqual(move_count(2), 3)
        self.assertEqual(move_count(3), 7)
        self.assertEqual(move_count(4), 15)

    def test_matches_length(self):
        for n in range(0, 6):
            self.assertEqual(move_count(n), len(generate_moves(n)))

    def test_negative_rejected(self):
        with self.assertRaises(HanoiError):
            move_count(-1)

    def test_non_int_rejected(self):
        with self.assertRaises(HanoiError):
            move_count(2.5)


class TestGenerateMoves(unittest.TestCase):
    def test_one_disk(self):
        self.assertEqual(generate_moves(1), [(1, 0, 2)])

    def test_two_disks(self):
        self.assertEqual(generate_moves(2), [(1, 0, 1), (2, 0, 2), (1, 1, 2)])

    def test_three_disks(self):
        self.assertEqual(
            generate_moves(3),
            [
                (1, 0, 2),
                (2, 0, 1),
                (1, 2, 1),
                (3, 0, 2),
                (1, 1, 0),
                (2, 1, 2),
                (1, 0, 2),
            ],
        )

    def test_empty(self):
        self.assertEqual(generate_moves(0), [])

    def test_step_moves(self):
        self.assertEqual(step_moves(2), [(0, 1), (0, 2), (1, 2)])

    def test_generated_sequence_is_valid(self):
        for n in range(0, 6):
            self.assertTrue(is_valid_sequence(n, step_moves(n)))


class TestMinMovesTo(unittest.TestCase):
    def test_to_middle(self):
        self.assertEqual(min_moves_to(1, 1), 1)
        self.assertEqual(min_moves_to(2, 1), 3)
        self.assertEqual(min_moves_to(3, 1), 7)

    def test_to_right(self):
        self.assertEqual(min_moves_to(3, 2), 7)

    def test_zero(self):
        self.assertEqual(min_moves_to(0, 1), 0)

    def test_bad_peg(self):
        with self.assertRaises(InvalidPegError):
            min_moves_to(3, 9)


class TestKthMove(unittest.TestCase):
    def test_first_and_last(self):
        self.assertEqual(kth_move(2, 0), (1, 0, 1))
        self.assertEqual(kth_move(2, 1), (2, 0, 2))
        self.assertEqual(kth_move(2, 2), (1, 1, 2))

    def test_out_of_range(self):
        with self.assertRaises(StepOutOfRangeError):
            kth_move(2, 3)
        with self.assertRaises(StepOutOfRangeError):
            kth_move(2, -1)


class TestIsValidSequence(unittest.TestCase):
    def test_good(self):
        self.assertTrue(is_valid_sequence(2, [(0, 1), (0, 2), (1, 2)]))

    def test_wrong_length(self):
        self.assertFalse(is_valid_sequence(2, [(0, 2)]))

    def test_big_on_small(self):
        self.assertFalse(is_valid_sequence(2, [(0, 2), (0, 1), (2, 1)]))

    def test_empty_pile(self):
        self.assertFalse(is_valid_sequence(2, [(1, 2), (0, 1), (1, 2)]))

    def test_bad_peg(self):
        with self.assertRaises(InvalidPegError):
            is_valid_sequence(2, [(0, 5), (0, 2), (1, 2)])

    def test_bad_step_shape(self):
        with self.assertRaises(InvalidMoveError):
            is_valid_sequence(2, [0, 2, 1])


class TestHanoi4(unittest.TestCase):
    def test_small(self):
        self.assertEqual(hanoi4(0), 0)
        self.assertEqual(hanoi4(1), 1)
        self.assertEqual(hanoi4(2), 3)
        self.assertEqual(hanoi4(3), 5)
        self.assertEqual(hanoi4(4), 9)


class TestRestricted(unittest.TestCase):
    def test_small(self):
        self.assertEqual(min_moves_restricted(0), 0)
        self.assertEqual(min_moves_restricted(1), 2)
        self.assertEqual(min_moves_restricted(2), 8)
        self.assertEqual(min_moves_restricted(3), 26)


if __name__ == "__main__":
    unittest.main()
