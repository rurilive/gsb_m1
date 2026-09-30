"""bittrix 现有朴素行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from bittrix.naive import (
    BitError,
    BitTools,
    Erro,
    all_adjacent_pairs_differ,
    bit_position_counts,
    common_prefix_length,
    gray_adjacent_one_bit,
    has_adjacent_alternating,
    highest_set_bit,
    interleave_check,
    is_power_of_two,
    lowest_set_bit,
    popcount_loop,
    popcount_str,
    reverse_bits,
)


class TestPopcount(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(popcount_str(0), 0)
        self.assertEqual(popcount_loop(0), 0)

    def test_small(self):
        self.assertEqual(popcount_str(0b1011), 3)
        self.assertEqual(popcount_loop(0b1011), 3)

    def test_all_ones(self):
        self.assertEqual(popcount_str(0xFF), 8)
        self.assertEqual(popcount_loop(0xFF), 8)

    def test_both_paths_agree(self):
        for value in [0, 1, 2, 3, 7, 8, 15, 16, 255, 256, 1023]:
            self.assertEqual(popcount_str(value), popcount_loop(value))

    def test_negative_rejected(self):
        with self.assertRaises(BitError):
            popcount_str(-1)
        with self.assertRaises(BitError):
            popcount_loop(-1)

    def test_non_int_rejected(self):
        with self.assertRaises(BitError):
            popcount_str("3")


class TestSingleBitQueries(unittest.TestCase):
    def test_lowest_set_bit(self):
        self.assertEqual(lowest_set_bit(1), 0)
        self.assertEqual(lowest_set_bit(2), 1)
        self.assertEqual(lowest_set_bit(12), 2)
        self.assertEqual(lowest_set_bit(1 << 20), 20)

    def test_highest_set_bit(self):
        self.assertEqual(highest_set_bit(1), 0)
        self.assertEqual(highest_set_bit(2), 1)
        self.assertEqual(highest_set_bit(12), 3)
        self.assertEqual(highest_set_bit(1 << 20), 20)

    def test_zero_has_no_set_bit(self):
        with self.assertRaises(BitError):
            lowest_set_bit(0)
        with self.assertRaises(BitError):
            highest_set_bit(0)


class TestPowerOfTwo(unittest.TestCase):
    def test_powers(self):
        for k in range(0, 20):
            self.assertTrue(is_power_of_two(1 << k))

    def test_non_powers(self):
        for value in [0, 3, 5, 6, 7, 9, 12, 100]:
            self.assertFalse(is_power_of_two(value))

    def test_negative_rejected(self):
        with self.assertRaises(BitError):
            is_power_of_two(-8)


class TestReverseBits(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(reverse_bits(0b110, 3), 0b011)
        self.assertEqual(reverse_bits(0b1000, 4), 0b0001)

    def test_zero_width(self):
        self.assertEqual(reverse_bits(5, 0), 0)

    def test_double_reverse_is_identity(self):
        for value in [0, 1, 5, 0b1011, 0b11001]:
            self.assertEqual(
                reverse_bits(reverse_bits(value, 8), 8), value & 0xFF)

    def test_round_width_bits(self):
        self.assertEqual(reverse_bits(0b1000, 4), 1)

    def test_bad_width_rejected(self):
        with self.assertRaises(BitError):
            reverse_bits(3, -1)


class TestCommonPrefix(unittest.TestCase):
    def test_disjoint(self):
        self.assertEqual(common_prefix_length(0b1000, 0b0111, 4), 0)

    def test_shared_high(self):
        self.assertEqual(common_prefix_length(0b1000, 0b1001, 4), 3)

    def test_identical(self):
        self.assertEqual(common_prefix_length(0b1010, 0b1010, 4), 4)

    def test_zero_width(self):
        self.assertEqual(common_prefix_length(1, 2, 0), 0)

    def test_negative_rejected(self):
        with self.assertRaises(BitError):
            common_prefix_length(-1, 2, 4)


class TestAdjacentBits(unittest.TestCase):
    def test_has_adjacent_alternating(self):
        self.assertTrue(has_adjacent_alternating(0b100, 3))
        self.assertFalse(has_adjacent_alternating(0b111, 3))
        self.assertFalse(has_adjacent_alternating(0b000, 3))

    def test_all_pairs_differ(self):
        self.assertTrue(all_adjacent_pairs_differ(0b101, 3))
        self.assertTrue(all_adjacent_pairs_differ(0b010, 3))
        self.assertFalse(all_adjacent_pairs_differ(0b110, 3))

    def test_single_bit_width(self):
        self.assertFalse(has_adjacent_alternating(0, 1))
        self.assertTrue(all_adjacent_pairs_differ(0, 1))
        self.assertTrue(all_adjacent_pairs_differ(1, 1))

    def test_gray_adjacent_one_bit(self):
        self.assertTrue(gray_adjacent_one_bit(0b00, 2))
        self.assertFalse(gray_adjacent_one_bit(0b11, 2))
        self.assertTrue(gray_adjacent_one_bit(0b000, 3))
        self.assertFalse(gray_adjacent_one_bit(0b101, 3))

    def test_gray_wraps_at_zero_width(self):
        self.assertTrue(gray_adjacent_one_bit(0, 0))


class TestBitPositionCounts(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(bit_position_counts([0b00, 0b01, 0b11], 2), [1, 2])

    def test_empty(self):
        self.assertEqual(bit_position_counts([], 4), [0, 0, 0, 0])

    def test_total_matches_popcount_sum(self):
        values = [0b1010, 0b0110, 0b1111, 0b0001]
        counts = bit_position_counts(values, 4)
        self.assertEqual(sum(counts), sum(popcount_str(v) for v in values))

    def test_bad_symbol_value(self):
        with self.assertRaises(BitError):
            bit_position_counts([1, -1], 4)


class TestInterleaveAndErrors(unittest.TestCase):
    def test_interleave_check(self):
        self.assertTrue(interleave_check(0b1010, 0b1010, 4))
        self.assertFalse(interleave_check(0b1010, 0b1011, 4))

    def test_bit_error_is_erro(self):
        self.assertTrue(issubclass(BitError, Erro))

    def test_erro_catches_all(self):
        try:
            lowest_set_bit(0)
        except Erro:
            pass
        else:
            self.fail("expected Erro")


class TestBitTools(unittest.TestCase):
    def test_matches_plain(self):
        tools = BitTools(8)
        self.assertEqual(tools.popcount(0b1011), popcount_loop(0b1011))
        self.assertEqual(tools.reverse_bits(0b11010010),
                         reverse_bits(0b11010010, 8))
        self.assertEqual(tools.common_prefix_length(0b1000, 0b1001),
                         common_prefix_length(0b1000, 0b1001, 8))

    def test_visit_count_grows_and_resets(self):
        tools = BitTools(16)
        tools.reset_visit_count()
        self.assertEqual(tools.visit_count(), 0)
        tools.popcount(0xFFFF)
        after = tools.visit_count()
        self.assertGreater(after, 0)
        tools.reset_visit_count()
        self.assertEqual(tools.visit_count(), 0)
        tools.popcount(0xFFFF)
        self.assertEqual(tools.visit_count(), after)

    def test_two_tools_do_not_share_state(self):
        a = BitTools(8)
        b = BitTools(8)
        a.popcount(0xFF)
        self.assertEqual(b.visit_count(), 0)

    def test_width_accessor(self):
        self.assertEqual(BitTools(5).width(), 5)

    def test_gray_adjacent_one_bit(self):
        self.assertTrue(BitTools(3).gray_adjacent_one_bit(0b000))
        self.assertFalse(BitTools(3).gray_adjacent_one_bit(0b101))

    def test_bit_position_counts(self):
        self.assertEqual(
            BitTools(2).bit_position_counts([0b00, 0b01, 0b11]), [1, 2])

    def test_bad_width_rejected(self):
        with self.assertRaises(BitError):
            BitTools(None)


class TestDeterminism(unittest.TestCase):
    def test_repeated_run_same_result(self):
        tools = BitTools(8)
        first = (
            tools.popcount(0b10110011),
            tools.reverse_bits(0b10110011),
            tools.common_prefix_length(0b1000, 0b1001),
            tools.bit_position_counts([1, 2, 4, 8]),
        )
        for _ in range(3):
            self.assertEqual(
                (
                    tools.popcount(0b10110011),
                    tools.reverse_bits(0b10110011),
                    tools.common_prefix_length(0b1000, 0b1001),
                    tools.bit_position_counts([1, 2, 4, 8]),
                ),
                first,
            )


if __name__ == "__main__":
    unittest.main()
