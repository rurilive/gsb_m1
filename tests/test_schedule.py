"""基线行为测试：锁住整分调度器的现状。

按约束，本文件一个字都不改，必须全绿。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cronix.schedule import Scheduler


class _Moment(object):
    """极简时刻对象，只带基线关心的 minute。"""

    def __init__(self, minute):
        self.minute = minute


class SchedulerBaselineTest(unittest.TestCase):

    def test_match_exact_minute(self):
        scheduler = Scheduler(30)
        self.assertTrue(scheduler.match(_Moment(30)))

    def test_no_match_other_minute(self):
        scheduler = Scheduler(30)
        self.assertFalse(scheduler.match(_Moment(29)))
        self.assertFalse(scheduler.match(_Moment(31)))

    def test_expression_stored_as_text(self):
        scheduler = Scheduler("0")
        self.assertEqual(scheduler.expression, "0")
        self.assertEqual(scheduler.minute, 0)
        self.assertTrue(scheduler.match(_Moment(0)))

    def test_describe(self):
        scheduler = Scheduler(5)
        self.assertEqual(scheduler.describe(), "at minute 5")

    def test_reject_non_integer(self):
        with self.assertRaises(ValueError):
            Scheduler("*/5")

    def test_reject_range(self):
        with self.assertRaises(ValueError):
            Scheduler("10-20")

    def test_reject_out_of_range(self):
        with self.assertRaises(ValueError):
            Scheduler(60)
        with self.assertRaises(ValueError):
            Scheduler(-1)


if __name__ == "__main__":
    unittest.main()
