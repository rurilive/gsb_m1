"""DeadlockDetector 行为的锁定测试（对拍基准见 waitgraph.oracle）。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from waitgraph import FullScan, ResourceRegistry  # noqa: E402


def closed_pair():
    """11 拿 db，12 拿 cache，两边换着要，凑成一个两进程的环。"""
    reg = ResourceRegistry()
    reg.acquire(11, "db")
    reg.acquire(12, "cache")
    reg.acquire(12, "db")
    reg.acquire(11, "cache")
    return reg


class DetectorTest(unittest.TestCase):

    def test_closed_pair_is_reported(self):
        reg = closed_pair()
        detector = reg.detector
        self.assertTrue(detector.deadlocked())
        self.assertEqual(set(detector.cycle_members()), {11, 12})
        self.assertEqual(set(detector.cycle_members()),
                         set(FullScan(reg).cycle_members()))

    def test_open_fan_in_is_not_reported(self):
        reg = ResourceRegistry()
        reg.acquire(31, "a")
        reg.acquire(32, "a")     # 32 等 31
        reg.acquire(31, "b")
        reg.acquire(33, "b")     # 33 等 31
        self.assertEqual(reg.waits(), [(32, "a", 31), (33, "b", 31)])
        self.assertFalse(reg.detector.deadlocked())
        self.assertEqual(reg.detector.cycle_members(), [])
        self.assertFalse(reg.health()["deadlocked"])

    def test_rebuild_from_snapshot(self):
        reg = ResourceRegistry()
        reg.load_state({"a": 41, "b": 42}, [(41, "b", 42), (42, "a", 41)])
        self.assertTrue(reg.detector.deadlocked())
        self.assertEqual(set(reg.detector.cycle_members()), {41, 42})

    def test_stats_report_visits_and_reset(self):
        reg = ResourceRegistry()
        reg.acquire(51, "a")
        reg.acquire(52, "a")
        detector = reg.detector
        self.assertGreaterEqual(detector.stats()["visits"], 2)
        self.assertEqual(detector.stats()["nodes"], 2)
        detector.reset_stats()
        self.assertEqual(detector.stats()["visits"], 0)


if __name__ == "__main__":
    unittest.main()
