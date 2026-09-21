"""百万份额压测：纯整数运算，十五秒内必须回来。"""

import random
import time
import unittest

from centledger import BatchRequest, Ledger

REQUESTS = 200000
ACCOUNTS = 5
BUDGET_SECONDS = 15


class PerfTest(unittest.TestCase):
    def test_million_shares_within_budget(self):
        rng = random.Random(20260920)
        names = ["acc%02d" % index for index in range(ACCOUNTS)]
        ledger = Ledger()
        started = time.time()
        for index in range(REQUESTS):
            weights = {name: rng.randrange(0, 50) for name in names}
            if not any(weights.values()):
                weights[names[0]] = 1
            ledger.apply_batch("P-%06d" % index, [
                BatchRequest("%d.%02d" % (rng.randrange(0, 1000),
                                          rng.randrange(0, 100)),
                             weights),
            ])
        elapsed = time.time() - started
        self.assertTrue(ledger.reconcile().ok)
        self.assertLess(elapsed, BUDGET_SECONDS,
                        "%d 份额耗时 %.1f 秒，超预算" % (
                            REQUESTS * ACCOUNTS, elapsed))


if __name__ == "__main__":
    unittest.main()
