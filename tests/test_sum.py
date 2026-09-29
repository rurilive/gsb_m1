"""prefixsum 现有行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from prefixsum.sum import ScanSum


def build():
    return ScanSum([1, 2, 3, 4, 5])


class TestScanSum(unittest.TestCase):
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
            ScanSum([1, "x"])
        with self.assertRaises(ValueError):
            ScanSum([1, True])

    def test_empty_default(self):
        self.assertEqual(len(ScanSum()), 0)

    def test_query_full_range(self):
        a = build()
        self.assertEqual(a.query(0, 5), 15)

    def test_query_subrange(self):
        a = build()
        self.assertEqual(a.query(1, 3), 5)
        self.assertEqual(a.query(2, 5), 12)

    def test_query_single_element(self):
        a = build()
        self.assertEqual(a.query(3, 4), 4)

    def test_query_empty_range(self):
        a = build()
        self.assertEqual(a.query(2, 2), 0)

    def test_query_cost_is_range_width(self):
        a = build()
        a.query(1, 4)
        self.assertEqual(a.last_cost(), 3)

    def test_query_cost_empty_is_zero(self):
        a = build()
        a.query(1, 1)
        self.assertEqual(a.last_cost(), 0)

    def test_query_bad_range_left_negative(self):
        a = build()
        with self.assertRaises(ValueError):
            a.query(-1, 2)

    def test_query_bad_range_right_past_end(self):
        a = build()
        with self.assertRaises(ValueError):
            a.query(0, 6)

    def test_query_bad_range_left_after_right(self):
        a = build()
        with self.assertRaises(ValueError):
            a.query(3, 2)

    def test_update_returns_new(self):
        a = build()
        self.assertEqual(a.update(2, 30), 33)
        self.assertEqual(a[2], 33)
        self.assertEqual(a.query(0, 5), 45)

    def test_update_negative_delta(self):
        a = build()
        self.assertEqual(a.update(4, -5), 0)
        self.assertEqual(a.query(4, 5), 0)

    def test_update_rejects_non_int(self):
        a = build()
        with self.assertRaises(ValueError):
            a.update(0, "x")
        with self.assertRaises(ValueError):
            a.update(0, False)

    def test_update_out_of_range(self):
        a = build()
        with self.assertRaises(IndexError):
            a.update(5, 1)

    def test_negative_values_allowed(self):
        a = ScanSum([-1, -2, 3])
        self.assertEqual(a.query(0, 3), 0)
        self.assertEqual(a.query(0, 2), -3)


if __name__ == "__main__":
    unittest.main()
