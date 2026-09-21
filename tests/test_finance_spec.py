"""财务口径的行为锁定测试。

规则（与 README 一致）：

- 分摊以分为最小单位，逐户四舍五入到分；
- 摊不平的尾差归权重最大的账户，并列取账户名排序靠前的；
  负总额的尾差方向跟着总额走；
- 权重非负，可以是 0，0 权重的账户不参与这一笔；
- 权重全为零时整笔挂账，各户都是零，不落给任何账户；
- 不足一分的请求折成零，各户记一笔零，请求照常计数；
- 同一批次号重放，返回与第一次完全一样的结果；
- 负权重报 MoneyError，空请求报 ValueError。
"""

import random
import time
import unittest
from decimal import Decimal, ROUND_HALF_UP

from centledger import BatchRequest, Ledger, MoneyError, to_cents


def reference_shares(total_cents, items):
    """整数分参考实现：独立写一遍口径，用来对拍。

    items 是 [(账户名, 权重)]，返回 {账户名: 整数分}。逐户用 Decimal
    高精度算出精确份额再四舍五入到分，尾差归权重最大户，并列取
    账户名排序靠前的；全零权重整笔挂账，各户都是零。
    """
    names = [name for name, _ in items]
    weights = [Decimal(str(weight)) for _, weight in items]
    weight_sum = sum(weights)
    if weight_sum == 0:
        return dict((name, 0) for name in names)
    shares = []
    for weight in weights:
        exact = Decimal(total_cents) * weight / weight_sum
        shares.append(int(exact.to_integral_value(rounding=ROUND_HALF_UP)))
    residual = total_cents - sum(shares)
    if residual:
        best_weight = max(weights)
        target = min(
            (index for index in range(len(items))
             if weights[index] == best_weight),
            key=lambda index: names[index],
        )
        shares[target] += residual
    return dict(zip(names, shares))


class FinanceSpecTest(unittest.TestCase):
    def test_residual_goes_to_first_name_on_weight_tie(self):
        ledger = Ledger()
        result = ledger.apply_batch("B-1", [
            BatchRequest("10.00", {"gamma": 1, "alpha": 1, "beta": 1}),
        ])
        self.assertEqual(result.credits, {
            "alpha": Decimal("3.34"),
            "beta": Decimal("3.33"),
            "gamma": Decimal("3.33"),
        })
        self.assertTrue(ledger.reconcile().ok)

    def test_residual_goes_to_largest_weight(self):
        ledger = Ledger()
        result = ledger.apply_batch("B-1", [
            BatchRequest("10.02", {"zeta": 2, "alpha": 1, "beta": 1}),
        ])
        self.assertEqual(result.credits, {
            "zeta": Decimal("5.00"),
            "alpha": Decimal("2.51"),
            "beta": Decimal("2.51"),
        })

    def test_negative_total_residual_follows_total(self):
        ledger = Ledger()
        result = ledger.apply_batch("B-1", [
            BatchRequest("-10.00", {"alpha": 1, "beta": 1, "gamma": 1}),
        ])
        self.assertEqual(result.credits, {
            "alpha": Decimal("-3.34"),
            "beta": Decimal("-3.33"),
            "gamma": Decimal("-3.33"),
        })
        self.assertTrue(ledger.reconcile().ok)

    def test_zero_weight_account_never_gets_residual(self):
        ledger = Ledger()
        result = ledger.apply_batch("B-1", [
            BatchRequest("-10.00",
                         {"coupon": 0, "alice": 1, "bob": 1, "carol": 1}),
        ])
        self.assertEqual(result.credits["coupon"], Decimal("0.00"))
        self.assertEqual(result.credits["alice"], Decimal("-3.34"))
        self.assertEqual(sum(result.credits.values()), Decimal("-10.00"))

    def test_all_zero_weights_booked_as_suspense(self):
        ledger = Ledger()
        result = ledger.apply_batch("B-1", [
            BatchRequest("4.00", {"a": 0, "b": 0}),
        ])
        self.assertEqual(result.credits, {
            "a": Decimal("0.00"), "b": Decimal("0.00")})
        report = ledger.reconcile()
        self.assertEqual(report.total_in, Decimal("4.00"))
        self.assertEqual(report.total_out, Decimal("0.00"))
        self.assertEqual(report.difference, Decimal("-4.00"))
        self.assertFalse(report.ok)

    def test_zero_total_still_recorded(self):
        ledger = Ledger()
        result = ledger.apply_batch("B-1", [
            BatchRequest("0.00", {"a": 1, "b": 1}),
        ])
        self.assertEqual(result.credits, {
            "a": Decimal("0.00"), "b": Decimal("0.00")})
        report = ledger.reconcile()
        self.assertEqual(report.requests, 1)
        self.assertTrue(report.ok)

    def test_sub_cent_request_leaves_a_trace(self):
        ledger = Ledger()
        result = ledger.apply_batch("B-1", [
            BatchRequest("0.004", {"alpha": 1, "beta": 1}),
        ])
        self.assertEqual(sorted(result.credits), ["alpha", "beta"])
        self.assertEqual(result.credits["alpha"], Decimal("0.00"))
        self.assertEqual(ledger.balance("alpha"), Decimal("0.00"))
        report = ledger.reconcile()
        self.assertEqual(report.requests, 1)
        self.assertTrue(report.ok)

    def test_negative_weight_rejected_and_batch_not_posted(self):
        ledger = Ledger()
        self.assertRaises(
            MoneyError, ledger.apply_batch, "B-1",
            [BatchRequest("1.00", {"a": 1}),
             BatchRequest("1.00", {"b": -1})])
        self.assertEqual(ledger.balances(), {})
        self.assertEqual(ledger.reconcile().requests, 0)

    def test_large_amount_exact_to_the_cent(self):
        ledger = Ledger()
        ledger.apply_batch("B-1", [
            BatchRequest("12345678901234567.89", {"alpha": 1, "beta": 2}),
        ])
        report = ledger.reconcile()
        self.assertEqual(to_cents(report.total_in), 1234567890123456789)
        self.assertEqual(to_cents(report.total_out), 1234567890123456789)
        self.assertTrue(report.ok)

    def test_two_decimal_weights_are_exact(self):
        ledger = Ledger()
        result = ledger.apply_batch("B-1", [
            BatchRequest("3.00", {"a": "0.10", "b": "0.20", "c": "0.70"}),
        ])
        self.assertEqual(result.credits, {
            "a": Decimal("0.30"),
            "b": Decimal("0.60"),
            "c": Decimal("2.10"),
        })

    def test_replay_is_idempotent_and_byte_identical(self):
        requests = [
            BatchRequest("10.00", {"gamma": 1, "alpha": 1, "beta": 1}),
            BatchRequest("-4.01", {"alpha": 2, "beta": 1}),
        ]
        ledger = Ledger()
        first = ledger.apply_batch("B-1", requests)
        snapshot = ledger.balances()
        second = ledger.apply_batch("B-1", requests)
        self.assertEqual(first.render(), second.render())
        self.assertEqual(ledger.balances(), snapshot)
        self.assertEqual(ledger.reconcile().requests, 2)

    def test_account_order_does_not_change_output(self):
        first = Ledger().apply_batch("B-1", [
            BatchRequest("-10.00", {"bob": 1, "carol": 1, "dave": 1}),
        ])
        second = Ledger().apply_batch("B-1", [
            BatchRequest("-10.00", {"dave": 1, "carol": 1, "bob": 1}),
        ])
        self.assertEqual(first.render(), second.render())
        self.assertEqual(first.credits, second.credits)

    def test_many_batches_do_not_drift(self):
        ledger = Ledger()
        for index in range(200):
            ledger.apply_batch("B-%04d" % index, [
                BatchRequest("10.00", {"alpha": 1, "beta": 1, "gamma": 1}),
            ])
        report = ledger.reconcile()
        self.assertEqual(report.total_out, Decimal("2000.00"))
        self.assertTrue(report.ok)


class CrossCheckTest(unittest.TestCase):
    """十万级随机用例，拿整数分参考实现逐户逐分对拍。"""

    def test_random_batches_match_reference(self):
        rng = random.Random(20260921)
        pool = ["acct%02d" % index for index in range(20)]
        ledger = Ledger()
        ref_balances = {}
        ref_total_in = 0
        cases = 0
        for batch_no in range(50000):
            requests = []
            expected = {}
            for _ in range(rng.randrange(1, 4)):
                names = rng.sample(pool, rng.randrange(1, 7))
                weights = {}
                for name in names:
                    choice = rng.randrange(4)
                    if choice == 0:
                        weights[name] = rng.randrange(0, 50)
                    elif choice == 1:
                        weights[name] = "%d.%02d" % (
                            rng.randrange(0, 20), rng.randrange(0, 100))
                    elif choice == 2:
                        weights[name] = Decimal(
                            "%d.%d" % (rng.randrange(0, 9),
                                       rng.randrange(0, 10)))
                    else:
                        weights[name] = 0
                kind = rng.randrange(10)
                if kind == 0:
                    total = "0.00"
                elif kind == 1:
                    total = "0.00%d" % rng.randrange(1, 10)
                elif kind == 2:
                    total = "-%d.%02d" % (rng.randrange(0, 500),
                                          rng.randrange(0, 100))
                elif kind == 3:
                    total = "%d%08d.%02d" % (rng.randrange(1, 10 ** 9),
                                             rng.randrange(0, 10 ** 8),
                                             rng.randrange(0, 100))
                else:
                    total = "%d.%02d" % (rng.randrange(0, 1000),
                                         rng.randrange(0, 100))
                requests.append(BatchRequest(total, weights))
                total_cents = to_cents(total)
                ref_total_in += total_cents
                if total_cents == 0:
                    shares = dict((name, 0) for name in names)
                else:
                    shares = reference_shares(
                        total_cents, sorted(weights.items()))
                for name, cents in shares.items():
                    expected[name] = expected.get(name, 0) + cents
                if any(Decimal(str(w)) != 0 for w in weights.values()):
                    self.assertEqual(
                        sum(shares.values()), total_cents,
                        "参考实现自身合计必须等于总额: %r" % total)
                cases += 1
            result = ledger.apply_batch("R-%06d" % batch_no, requests)
            actual = dict(
                (name, to_cents(credit))
                for name, credit in result.credits.items())
            self.assertEqual(
                actual, expected,
                "批次 R-%06d 各户份额与参考实现不一致" % batch_no)
            for name, cents in expected.items():
                ref_balances[name] = ref_balances.get(name, 0) + cents
        for name, cents in ref_balances.items():
            self.assertEqual(
                to_cents(ledger.balance(name)), cents,
                "账户 %s 余额与参考实现不一致" % name)
        report = ledger.reconcile()
        self.assertEqual(report.requests, cases)
        self.assertEqual(to_cents(report.total_in), ref_total_in)
        self.assertEqual(
            to_cents(report.total_out), sum(ref_balances.values()))
        self.assertGreaterEqual(cases, 100000)


class PerfTest(unittest.TestCase):
    """百万份额压测：十五秒内回来。"""

    def test_million_shares_under_15_seconds(self):
        rng = random.Random(20260920)
        names = ["acc%02d" % index for index in range(5)]
        ledger = Ledger()
        started = time.time()
        for index in range(200000):
            weights = dict(
                (name, rng.randrange(0, 50)) for name in names)
            if not any(weights.values()):
                weights[names[0]] = 1
            ledger.apply_batch("P-%06d" % index, [
                BatchRequest("%d.%02d" % (rng.randrange(0, 1000),
                                          rng.randrange(0, 100)),
                             weights),
            ])
        elapsed = time.time() - started
        self.assertTrue(ledger.reconcile().ok)
        self.assertLess(elapsed, 15,
                        "百万份额耗时 %.1f 秒，超过 15 秒" % elapsed)


if __name__ == "__main__":
    unittest.main()
