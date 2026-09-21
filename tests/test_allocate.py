import unittest
from decimal import Decimal

from centledger.allocate import Allocation, allocate
from centledger.money import MoneyError


class AllocateTest(unittest.TestCase):
    def test_even_split(self):
        result = allocate("10.00", [1, 1])
        self.assertEqual(result.shares, [Decimal("5.00"), Decimal("5.00")])
        self.assertEqual(result.residual, Decimal("0.00"))
        self.assertEqual(result.total_allocated(), result.total)

    def test_weighted_split_divides_evenly(self):
        result = allocate("9.99", [1, 2])
        self.assertEqual(result.shares, [Decimal("3.33"), Decimal("6.66")])
        self.assertEqual(result.residual, Decimal("0.00"))

    def test_many_accounts_divides_evenly(self):
        result = allocate("100.00", [1, 1, 1, 1])
        self.assertEqual(result.shares, [Decimal("25.00")] * 4)

    def test_fractional_weights(self):
        result = allocate("3.00", ["0.1", "0.2", "0.7"])
        self.assertEqual(
            result.shares, [Decimal("0.30"), Decimal("0.60"), Decimal("2.10")])
        self.assertEqual(result.residual, Decimal("0.00"))

    def test_zero_weight_account_gets_nothing(self):
        result = allocate("4.00", [1, 1, 0])
        self.assertEqual(result.shares, [Decimal("2.00"), Decimal("2.00"), Decimal("0.00")])
        self.assertEqual(result.residual, Decimal("0.00"))

    def test_negative_total_divides_evenly(self):
        result = allocate("-4.00", [1, 1])
        self.assertEqual(result.shares, [Decimal("-2.00"), Decimal("-2.00")])
        self.assertEqual(result.residual, Decimal("0.00"))

    def test_zero_total(self):
        result = allocate("0.00", [1, 1])
        self.assertEqual(result.shares, [Decimal("0.00"), Decimal("0.00")])
        self.assertEqual(result.residual, Decimal("0.00"))

    def test_all_weights_zero_books_whole_amount_as_residual(self):
        result = allocate("4.00", [0, 0])
        self.assertEqual(result.shares, [Decimal("0.00"), Decimal("0.00")])
        self.assertEqual(result.residual, Decimal("4.00"))
        self.assertIsInstance(result, Allocation)

    def test_negative_weight_rejected(self):
        self.assertRaises(MoneyError, allocate, "4.00", [1, -1])

    def test_empty_weights_rejected(self):
        self.assertRaises(ValueError, allocate, "4.00", [])

    def test_junk_weight_rejected(self):
        self.assertRaises(MoneyError, allocate, "4.00", ["x"])


if __name__ == "__main__":
    unittest.main()
