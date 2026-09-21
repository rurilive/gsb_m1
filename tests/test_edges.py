"""边界规矩：尾差归宿、子分请求、重放、大额、账户顺序，全部锁死。"""

import unittest
from decimal import Decimal

from centledger import BatchRequest, Ledger, MoneyError


class ResidualRuleTest(unittest.TestCase):
    def test_residual_goes_to_max_weight_account(self):
        ledger = Ledger()
        result = ledger.apply_batch("B-1", [
            BatchRequest("10.00", {"alpha": 1, "beta": 1, "gamma": 1}),
        ])
        self.assertEqual(result.credits, {
            "alpha": Decimal("3.34"),
            "beta": Decimal("3.33"),
            "gamma": Decimal("3.33"),
        })
        self.assertTrue(ledger.reconcile().ok)

    def test_tie_breaks_by_account_name_not_dict_order(self):
        first = Ledger().apply_batch("B-1", [
            BatchRequest("10.00", {"gamma": 1, "alpha": 1, "beta": 1}),
        ])
        second = Ledger().apply_batch("B-1", [
            BatchRequest("10.00", {"beta": 1, "gamma": 1, "alpha": 1}),
        ])
        self.assertEqual(first.credits["alpha"], Decimal("3.34"))
        self.assertEqual(first.render(), second.render())

    def test_bigger_weight_wins_over_smaller_name(self):
        ledger = Ledger()
        result = ledger.apply_batch("B-1", [
            BatchRequest("0.01", {"a": 1, "z": 2}),
        ])
        self.assertEqual(result.credits, {
            "a": Decimal("0.00"),
            "z": Decimal("0.01"),
        })

    def test_negative_residual_comes_back_from_target(self):
        ledger = Ledger()
        result = ledger.apply_batch("B-1", [
            BatchRequest("0.01", {"a": 1, "b": 1}),
        ])
        self.assertEqual(result.credits, {
            "a": Decimal("0.00"),
            "b": Decimal("0.01"),
        })
        self.assertTrue(ledger.reconcile().ok)

    def test_reversal_batch_zero_weight_untouched(self):
        ledger = Ledger()
        result = ledger.apply_batch("B-1", [
            BatchRequest("-10.00", {"coupon": 0, "alice": 1, "bob": 1, "carol": 1}),
        ])
        self.assertEqual(result.credits["coupon"], Decimal("0.00"))
        self.assertEqual(result.credits["alice"], Decimal("-3.34"))
        self.assertEqual(result.credits["bob"], Decimal("-3.33"))
        self.assertEqual(result.credits["carol"], Decimal("-3.33"))
        self.assertTrue(ledger.reconcile().ok)

    def test_all_zero_weights_suspends_whole_amount(self):
        ledger = Ledger()
        result = ledger.apply_batch("B-1", [
            BatchRequest("4.00", {"a": 0, "b": 0}),
        ])
        self.assertEqual(result.credits, {"a": Decimal("0.00"), "b": Decimal("0.00")})
        report = ledger.reconcile()
        self.assertEqual(report.difference, Decimal("-4.00"))
        self.assertFalse(report.ok)


class SubCentTest(unittest.TestCase):
    def test_sub_cent_request_rejected(self):
        ledger = Ledger()
        self.assertRaises(MoneyError, ledger.apply_batch, "B-1", [
            BatchRequest("0.004", {"a": 1, "b": 1}),
        ])
        self.assertRaises(MoneyError, ledger.apply_batch, "B-2", [
            BatchRequest("-0.004", {"a": 1}),
        ])

    def test_failed_batch_leaves_no_trace(self):
        ledger = Ledger()
        ledger.apply_batch("B-1", [BatchRequest("4.00", {"a": 1})])
        self.assertRaises(MoneyError, ledger.apply_batch, "B-2", [
            BatchRequest("2.00", {"a": 1}),
            BatchRequest("0.004", {"a": 1}),
        ])
        self.assertEqual(ledger.balance("a"), Decimal("4.00"))
        report = ledger.reconcile()
        self.assertEqual(report.requests, 1)
        self.assertEqual(report.total_in, Decimal("4.00"))

    def test_exact_zero_total_is_quiet_noop(self):
        ledger = Ledger()
        result = ledger.apply_batch("B-1", [BatchRequest("0.00", {"a": 1})])
        self.assertEqual(result.credits, {})
        self.assertEqual(ledger.reconcile().requests, 1)


class ReplayTest(unittest.TestCase):
    def test_replay_returns_identical_result(self):
        ledger = Ledger()
        requests = [BatchRequest("6.00", {"alpha": 1, "beta": 1, "gamma": 1})]
        first = ledger.apply_batch("B-1", requests)
        second = ledger.apply_batch("B-1", [
            BatchRequest("6.00", {"gamma": 1, "beta": 1, "alpha": 1}),
        ])
        self.assertEqual(first.render(), second.render())
        self.assertEqual(ledger.balance("alpha"), Decimal("2.00"))
        self.assertEqual(ledger.reconcile().requests, 1)

    def test_same_batch_id_different_content_rejected(self):
        ledger = Ledger()
        ledger.apply_batch("B-1", [BatchRequest("6.00", {"a": 1})])
        self.assertRaises(ValueError, ledger.apply_batch, "B-1", [
            BatchRequest("6.01", {"a": 1}),
        ])
        self.assertRaises(ValueError, ledger.apply_batch, "B-1", [
            BatchRequest("6.00", {"a": 1, "b": 1}),
        ])
        self.assertEqual(ledger.balance("a"), Decimal("6.00"))

    def test_weight_spelling_does_not_break_replay(self):
        ledger = Ledger()
        ledger.apply_batch("B-1", [BatchRequest("4.00", {"a": 1, "b": "2.0"})])
        replayed = ledger.apply_batch("B-1", [
            BatchRequest("4.00", {"a": Decimal("1.00"), "b": 2}),
        ])
        self.assertEqual(ledger.balance("b"), Decimal("2.67"))
        self.assertIsNotNone(replayed)


class BigAmountTest(unittest.TestCase):
    def test_seventeen_digit_amount_exact(self):
        ledger = Ledger()
        ledger.apply_batch("B-1", [
            BatchRequest("12345678901234567.89", {"alpha": 1, "beta": 2}),
        ])
        report = ledger.reconcile()
        self.assertEqual(report.total_in, Decimal("12345678901234567.89"))
        self.assertTrue(report.ok)

    def test_render_is_order_independent(self):
        first = Ledger().apply_batch("B-5", [
            BatchRequest("-10.00", {"bob": 1, "carol": 1, "dave": 1}),
        ])
        second = Ledger().apply_batch("B-5", [
            BatchRequest("-10.00", {"dave": 1, "carol": 1, "bob": 1}),
        ])
        self.assertEqual(first.render(), second.render())


if __name__ == "__main__":
    unittest.main()
