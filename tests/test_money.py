import unittest
from decimal import Decimal

from centledger.money import MoneyError, format_cents, from_cents, to_cents


class ToCentsTest(unittest.TestCase):
    def test_whole_and_decimal_amounts(self):
        self.assertEqual(to_cents("10.00"), 1000)
        self.assertEqual(to_cents(7), 700)
        self.assertEqual(to_cents(Decimal("12.34")), 1234)
        self.assertEqual(to_cents("-0.05"), -5)

    def test_rounds_half_up_to_cent(self):
        self.assertEqual(to_cents("0.005"), 1)
        self.assertEqual(to_cents("2.675"), 268)
        self.assertEqual(to_cents("0.004"), 0)

    def test_float_amounts(self):
        self.assertEqual(to_cents(1.5), 150)
        self.assertEqual(to_cents(0.25), 25)

    def test_rejects_junk(self):
        self.assertRaises(MoneyError, to_cents, "abc")
        self.assertRaises(MoneyError, to_cents, float("nan"))
        self.assertRaises(MoneyError, to_cents, None)


class FromCentsTest(unittest.TestCase):
    def test_roundtrip(self):
        self.assertEqual(from_cents(1000), Decimal("10.00"))
        self.assertEqual(from_cents(-5), Decimal("-0.05"))
        self.assertEqual(from_cents(0), Decimal("0.00"))

    def test_rejects_non_integer(self):
        self.assertRaises(MoneyError, from_cents, "12")
        self.assertRaises(MoneyError, from_cents, 1.5)


class FormatCentsTest(unittest.TestCase):
    def test_layout(self):
        self.assertEqual(format_cents(0), "0.00")
        self.assertEqual(format_cents(5), "0.05")
        self.assertEqual(format_cents(1234), "12.34")
        self.assertEqual(format_cents(-1234), "-12.34")
        self.assertEqual(format_cents(-5), "-0.05")


if __name__ == "__main__":
    unittest.main()
