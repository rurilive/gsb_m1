"""十万级随机用例对拍：生产实现 vs 整数分参考实现。

逐笔校验：每户入账逐分一致、每笔合计恰好等于总额；期间穿插重放，
校验重放结果逐字节相同且余额不再变动。
"""

import random
import unittest
from decimal import Decimal
from fractions import Fraction

from centledger import BatchRequest, Ledger, as_weight, format_cents, from_cents

import refimpl

CASES = 100000
SEED = 20260921


def random_weight(rng):
    kind = rng.randrange(10)
    if kind < 2:
        return 0
    if kind < 6:
        return rng.randrange(1, 60)
    if kind < 9:
        return "%d.%02d" % (rng.randrange(0, 60), rng.randrange(0, 100))
    return Decimal("%d.%02d" % (rng.randrange(0, 60), rng.randrange(0, 100)))


def random_total_cents(rng):
    if rng.randrange(20) == 0:
        return rng.randrange(-10 ** 15, 10 ** 15)
    return rng.randrange(-200000, 200001)


class FuzzTest(unittest.TestCase):
    def test_random_batches_match_reference(self):
        rng = random.Random(SEED)
        ledger = Ledger()
        names_pool = ["acc%02d" % index for index in range(8)]
        ref_balances = {}
        suspended = 0
        history = []
        for case in range(CASES):
            count = rng.randrange(1, 7)
            names = rng.sample(names_pool, count)
            weights = {name: random_weight(rng) for name in names}
            if rng.randrange(50) == 0:
                weights = {name: 0 for name in names}
            total_cents = random_total_cents(rng)
            while total_cents == 0:
                total_cents = random_total_cents(rng)
            batch_id = "F-%06d" % case
            requests = [BatchRequest(format_cents(total_cents), weights)]
            result = ledger.apply_batch(batch_id, requests)
            history.append((batch_id, requests, result.render()))

            parsed = [as_weight(weights[name]) for name in names]
            fractions = [Fraction(weight) for weight in parsed]
            shares = refimpl.reference_shares(total_cents, fractions)
            if shares is None:
                expected = dict.fromkeys(names, 0)
                suspended += total_cents
            else:
                expected = dict(zip(names, shares))
                residual = total_cents - sum(shares)
                target = refimpl.residual_target(names, fractions)
                if residual:
                    expected[target] += residual
                self.assertEqual(sum(expected.values()), total_cents,
                                 "case %d 合计不等于总额" % case)
            for name in names:
                self.assertEqual(result.credits[name], from_cents(expected[name]),
                                 "case %d 账户 %s 入账不一致" % (case, name))
                ref_balances[name] = ref_balances.get(name, 0) + expected[name]
            if case % 500 == 0:
                self.assert_balances(ledger, ref_balances)
        self.assert_balances(ledger, ref_balances)

        report = ledger.reconcile()
        self.assertEqual(report.requests, CASES)
        self.assertEqual(report.difference, from_cents(-suspended))

        snapshot = ledger.balances()
        for batch_id, requests, text in rng.sample(history, 2000):
            replayed = ledger.apply_batch(batch_id, requests)
            self.assertEqual(replayed.render(), text,
                             "批次 %s 重放输出不一致" % batch_id)
        self.assertEqual(ledger.balances(), snapshot, "重放后余额变了")
        self.assertEqual(ledger.reconcile().requests, CASES)

    def assert_balances(self, ledger, ref_balances):
        for name, cents in ref_balances.items():
            self.assertEqual(ledger.balance(name), from_cents(cents),
                             "账户 %s 余额不一致" % name)


if __name__ == "__main__":
    unittest.main()
