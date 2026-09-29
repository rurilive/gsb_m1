"""rankerx 现有行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from rankerx.next import BruteNext


def build():
    return BruteNext([2, 1, 3, 5, 4])


class TestBruteNext(unittest.TestCase):
    def test_len(self):
        a = build()
        self.assertEqual(len(a), 5)

    def test_index_roundtrip(self):
        a = build()
        self.assertEqual(a[0], 2)
        self.assertEqual(a[4], 4)

    def test_index_negative(self):
        a = build()
        self.assertEqual(a[-1], 4)

    def test_index_out_of_range(self):
        a = build()
        with self.assertRaises(IndexError):
            a[5]

    def test_to_list_is_copy(self):
        a = build()
        copy = a.to_list()
        self.assertEqual(copy, [2, 1, 3, 5, 4])
        copy[0] = 99
        self.assertEqual(a[0], 2)

    def test_initial_values_must_be_int(self):
        with self.assertRaises(ValueError):
            BruteNext([1, "x"])
        with self.assertRaises(ValueError):
            BruteNext([1, True])

    def test_empty_default(self):
        self.assertEqual(len(BruteNext()), 0)

    def test_next_greater_found(self):
        a = build()
        self.assertEqual(a.next_greater(0), 3)
        self.assertEqual(a.next_greater(1), 3)
        self.assertEqual(a.next_greater(2), 5)

    def test_next_greater_none_is_minus_one(self):
        a = build()
        self.assertEqual(a.next_greater(3), -1)
        self.assertEqual(a.next_greater(4), -1)

    def test_next_greater_all(self):
        a = build()
        self.assertEqual(a.next_greater_all(), [3, 3, 5, -1, -1])

    def test_next_greater_all_empty(self):
        self.assertEqual(BruteNext().next_greater_all(), [])

    def test_next_greater_single(self):
        a = BruteNext([7])
        self.assertEqual(a.next_greater(0), -1)

    def test_next_greater_all_equal(self):
        a = BruteNext([4, 4, 4])
        self.assertEqual(a.next_greater_all(), [-1, -1, -1])

    def test_next_greater_index_out_of_range(self):
        a = build()
        with self.assertRaises(IndexError):
            a.next_greater(5)

    def test_index_must_be_int(self):
        a = build()
        with self.assertRaises(ValueError):
            a.next_greater("x")
        with self.assertRaises(ValueError):
            a.next_greater(True)

    def test_negative_values_allowed(self):
        a = BruteNext([-3, -1, -2])
        self.assertEqual(a.next_greater_all(), [-1, -1, -1])


if __name__ == "__main__":
    unittest.main()
