"""segtre 现有行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from segtre.array import SegArray


def build():
    return SegArray([1, 2, 3, 4, 5])


class TestSegArray(unittest.TestCase):
    def test_len(self):
        a = build()
        self.assertEqual(len(a), 5)

    def test_index_roundtrip(self):
        a = build()
        self.assertEqual(a[0], 1)
        self.assertEqual(a[4], 5)

    def test_index_negative(self):
        a = build()
        self.assertEqual(a[-1], 5)

    def test_index_out_of_range(self):
        a = build()
        with self.assertRaises(IndexError):
            a[5]

    def test_to_list_is_copy(self):
        a = build()
        copy = a.to_list()
        self.assertEqual(copy, [1, 2, 3, 4, 5])
        copy[0] = 99
        self.assertEqual(a[0], 1)

    def test_initial_values_must_be_int(self):
        with self.assertRaises(ValueError):
            SegArray([1, "x"])
        with self.assertRaises(ValueError):
            SegArray([1, True])

    def test_empty_default(self):
        self.assertEqual(len(SegArray()), 0)

    def test_sum_full_range(self):
        a = build()
        self.assertEqual(a.range_sum(0, 5), 15)

    def test_sum_subrange(self):
        a = build()
        self.assertEqual(a.range_sum(1, 3), 5)
        self.assertEqual(a.range_sum(2, 5), 12)

    def test_sum_single_element(self):
        a = build()
        self.assertEqual(a.range_sum(3, 4), 4)

    def test_sum_empty_range(self):
        a = build()
        self.assertEqual(a.range_sum(2, 2), 0)

    def test_sum_cost_is_range_width(self):
        a = build()
        a.range_sum(1, 4)
        self.assertEqual(a.last_cost(), 3)

    def test_sum_cost_empty_is_zero(self):
        a = build()
        a.range_sum(1, 1)
        self.assertEqual(a.last_cost(), 0)

    def test_sum_bad_range_left_negative(self):
        a = build()
        with self.assertRaises(ValueError):
            a.range_sum(-1, 2)

    def test_sum_bad_range_right_past_end(self):
        a = build()
        with self.assertRaises(ValueError):
            a.range_sum(0, 6)

    def test_sum_bad_range_left_after_right(self):
        a = build()
        with self.assertRaises(ValueError):
            a.range_sum(3, 2)

    def test_set_value_returns_old(self):
        a = build()
        self.assertEqual(a.set_value(2, 30), 3)
        self.assertEqual(a[2], 30)
        self.assertEqual(a.range_sum(0, 5), 42)

    def test_set_value_rejects_non_int(self):
        a = build()
        with self.assertRaises(ValueError):
            a.set_value(0, "x")
        with self.assertRaises(ValueError):
            a.set_value(0, False)

    def test_set_value_out_of_range(self):
        a = build()
        with self.assertRaises(IndexError):
            a.set_value(5, 1)

    def test_add_value_returns_new(self):
        a = build()
        self.assertEqual(a.add_value(1, 10), 12)
        self.assertEqual(a[1], 12)
        self.assertEqual(a.range_sum(1, 2), 12)

    def test_add_value_negative_delta(self):
        a = build()
        self.assertEqual(a.add_value(4, -5), 0)

    def test_add_value_rejects_non_int(self):
        a = build()
        with self.assertRaises(ValueError):
            a.add_value(0, 1.5)

    def test_add_value_out_of_range(self):
        a = build()
        with self.assertRaises(IndexError):
            a.add_value(5, 1)

    def test_negative_values_allowed(self):
        a = SegArray([-1, -2, 3])
        self.assertEqual(a.range_sum(0, 3), 0)
        self.assertEqual(a.range_sum(0, 2), -3)


if __name__ == "__main__":
    unittest.main()
