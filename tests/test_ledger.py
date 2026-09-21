import unittest
from decimal import Decimal

from centledger.ledger import BatchRequest, Ledger


class LedgerTest(unittest.TestCase):
    def test_single_batch_balances(self):
        ledger = Ledger()
        result = ledger.apply_batch("B-1", [
            BatchRequest("10.00", {"a": 1, "b": 1}),
        ])
        self.assertEqual(result.credits, {"a": Decimal("5.00"), "b": Decimal("5.00")})
        self.assertEqual(result.balances, {"a": Decimal("5.00"), "b": Decimal("5.00")})
        self.assertEqual(ledger.balance("a"), Decimal("5.00"))
        self.assertEqual(ledger.balance("c"), Decimal("0.00"))

    def test_batches_accumulate(self):
        ledger = Ledger()
        ledger.apply_batch("B-1", [BatchRequest("10.00", {"a": 1, "b": 1})])
        result = ledger.apply_batch("B-2", [BatchRequest("2.00", {"a": 1, "b": 1})])
        self.assertEqual(result.balances, {"a": Decimal("6.00"), "b": Decimal("6.00")})
        self.assertEqual(ledger.balances(), {"a": Decimal("6.00"), "b": Decimal("6.00")})

    def test_zero_weight_account_stays_put(self):
        ledger = Ledger()
        result = ledger.apply_batch("B-1", [
            BatchRequest("4.00", {"a": 1, "b": 1, "c": 0}),
        ])
        self.assertEqual(result.credits["c"], Decimal("0.00"))
        self.assertEqual(ledger.balance("c"), Decimal("0.00"))

    def test_negative_request_reduces_balance(self):
        ledger = Ledger()
        ledger.apply_batch("B-1", [BatchRequest("4.00", {"a": 1, "b": 1})])
        result = ledger.apply_batch("B-2", [BatchRequest("-4.00", {"a": 1, "b": 1})])
        self.assertEqual(result.credits, {"a": Decimal("-2.00"), "b": Decimal("-2.00")})
        self.assertEqual(ledger.balance("a"), Decimal("0.00"))

    def test_reconcile_after_clean_batches(self):
        ledger = Ledger()
        ledger.apply_batch("B-1", [
            BatchRequest("10.00", {"a": 1, "b": 1}),
            BatchRequest("5.00", {"a": 1, "b": 4}),
        ])
        report = ledger.reconcile()
        self.assertEqual(report.requests, 2)
        self.assertEqual(report.total_in, Decimal("15.00"))
        self.assertEqual(report.total_out, Decimal("15.00"))
        self.assertTrue(report.ok)
        self.assertEqual(report.difference, Decimal("0.00"))

    def test_render_lists_every_account(self):
        ledger = Ledger()
        result = ledger.apply_batch("B-7", [
            BatchRequest("6.00", {"a": 1, "b": 2}),
        ])
        lines = result.render().splitlines()
        self.assertEqual(lines[0], "batch B-7")
        self.assertEqual(set(lines[1:]), {
            "a credit=2.00 balance=2.00",
            "b credit=4.00 balance=4.00",
        })

    def test_request_without_accounts_rejected(self):
        ledger = Ledger()
        self.assertRaises(ValueError, ledger.apply_batch, "B-1", [BatchRequest("1.00", {})])

    def test_weights_are_copied(self):
        weights = {"a": 1, "b": 1}
        request = BatchRequest("2.00", weights)
        weights["c"] = 1
        self.assertEqual(sorted(request.accounts), ["a", "b"])


if __name__ == "__main__":
    unittest.main()
