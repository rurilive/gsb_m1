"""对拍门槛：随机序列下返回跟直连一致，上游调用数压在直连的六成以内。"""

import unittest

from resolvcache.refcheck import RATIO_BOUND, run_diff


class TestDiffAgainstDirectUpstream(unittest.TestCase):
    def check_seed(self, seed):
        report = run_diff(seed=seed)
        self.assertEqual(report.mismatches, [], report.summary())
        self.assertEqual(report.direct_calls, report.steps)
        self.assertLess(report.cache_calls, report.direct_calls,
                        report.summary())
        self.assertLessEqual(report.ratio, RATIO_BOUND, report.summary())
        self.assertTrue(report.ok(), report.summary())

    def test_default_seed(self):
        self.check_seed(20260921)

    def test_seed_one(self):
        self.check_seed(1)

    def test_seed_seven(self):
        self.check_seed(7)


if __name__ == "__main__":
    unittest.main()
