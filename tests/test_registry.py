"""ResourceRegistry 登记语义的锁定测试。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from waitgraph import AlreadyHeld, NotHeld, ResourceRegistry  # noqa: E402


class RegistryTest(unittest.TestCase):

    def test_acquire_free_resource(self):
        reg = ResourceRegistry()
        self.assertTrue(reg.acquire(11, "db"))
        self.assertEqual(reg.holder("db"), 11)
        self.assertEqual(reg.holds(11), ["db"])

    def test_second_acquire_queues_behind_holder(self):
        reg = ResourceRegistry()
        reg.acquire(11, "db")
        self.assertFalse(reg.acquire(12, "db"))
        self.assertEqual(reg.waiters("db"), [12])
        self.assertEqual(reg.pending(12), {"db": 11})
        self.assertEqual(reg.waits(), [(12, "db", 11)])

    def test_release_hands_to_queue_head(self):
        reg = ResourceRegistry()
        reg.acquire(11, "db")
        reg.acquire(12, "db")
        reg.acquire(13, "db")
        self.assertEqual(reg.release(11, "db"), 12)
        self.assertEqual(reg.holder("db"), 12)
        self.assertEqual(reg.pending(12), {})
        self.assertEqual(reg.pending(13), {"db": 12})
        self.assertEqual(reg.waiters("db"), [13])
        self.assertEqual(reg.release(12, "db"), 13)
        self.assertIsNone(reg.release(13, "db"))
        self.assertIsNone(reg.holder("db"))

    def test_invalid_registrations_raise(self):
        reg = ResourceRegistry()
        with self.assertRaises(NotHeld):
            reg.release(11, "db")
        reg.acquire(11, "db")
        with self.assertRaises(AlreadyHeld):
            reg.acquire(11, "db")
        reg.acquire(12, "db")
        with self.assertRaises(AlreadyHeld):
            reg.acquire(12, "db")

    def test_one_process_can_wait_on_several_resources(self):
        reg = ResourceRegistry()
        reg.acquire(11, "db")
        reg.acquire(12, "cache")
        self.assertFalse(reg.acquire(13, "db"))
        self.assertFalse(reg.acquire(13, "cache"))
        self.assertEqual(reg.pending(13), {"db": 11, "cache": 12})

    def test_snapshot_roundtrip(self):
        reg = ResourceRegistry()
        reg.load_state({"db": 11, "cache": 12},
                       [(13, "db", 11), (14, "cache", 12)])
        self.assertEqual(reg.holder("db"), 11)
        self.assertEqual(reg.waiters("db"), [13])
        self.assertEqual(reg.waiters("cache"), [14])
        self.assertEqual(sorted(reg.waits()),
                         [(13, "db", 11), (14, "cache", 12)])
        self.assertFalse(reg.health()["deadlocked"])

    def test_closed_pair_and_drop_aborts_both_directions(self):
        reg = ResourceRegistry()
        reg.acquire(11, "db")
        reg.acquire(12, "cache")
        reg.acquire(12, "db")     # 12 等 11 的 db
        reg.acquire(11, "cache")  # 11 等 12 的 cache，闭环
        reg.acquire(13, "db")     # 13 排在 12 后面等 db
        self.assertTrue(reg.health()["deadlocked"])
        aborted = reg.drop(12)
        self.assertEqual(sorted(aborted), [(11, "cache"), (12, "db")])
        self.assertEqual(reg.waits(), [(13, "db", 11)])
        self.assertIsNone(reg.holder("cache"))
        self.assertEqual(reg.pending(11), {})
        self.assertEqual(reg.pending(12), {})
        self.assertEqual(reg.holds(12), [])


if __name__ == "__main__":
    unittest.main()
