"""ExpiryWheel：按到期槽回收，开销只挂真到期的桶。"""

import time
import unittest

from leasekeeper.wheel import ExpiryWheel


class BucketTest(unittest.TestCase):
    def test_pop_only_due_buckets_sorted_independently(self):
        wheel = ExpiryWheel(tick=1.0)
        wheel.add("b", 2.0)
        wheel.add("a", 1.0)
        wheel.add("c", 10.0)
        self.assertEqual(sorted(wheel.pop_due(2.0)), ["a", "b"])
        self.assertEqual(wheel.pop_due(2.0), [])
        self.assertEqual(wheel.pop_due(10.0), ["c"])

    def test_boundary_slot_upper_bound_is_strict(self):
        wheel = ExpiryWheel(tick=1.0)
        wheel.add("r", 1.0)
        # 槽上界是 1.0；now 差一点不算到期，到点立即到期。
        self.assertEqual(wheel.pop_due(0.999), [])
        self.assertEqual(wheel.pop_due(1.0), ["r"])

    def test_discard_then_refill_same_slot_not_lost(self):
        wheel = ExpiryWheel(tick=1.0)
        wheel.add("r1", 1.0)
        wheel.discard("r1", 1.0)
        wheel.add("r2", 1.0)
        self.assertEqual(wheel.pop_due(1.0), ["r2"])

    def test_renew_moving_buckets_leaves_no_ghost(self):
        wheel = ExpiryWheel(tick=1.0)
        wheel.add("r", 1.0)
        wheel.discard("r", 1.0)
        wheel.add("r", 5.0)
        self.assertEqual(wheel.pop_due(1.0), [])
        self.assertEqual(wheel.pop_due(5.0), ["r"])

    def test_empty_slot_removed_but_slot_reusable_later(self):
        wheel = ExpiryWheel(tick=1.0)
        wheel.add("r", 1.0)
        wheel.discard("r", 1.0)
        self.assertEqual(wheel.pop_due(1.0), [])
        wheel.add("r", 1.0)
        self.assertEqual(wheel.pop_due(1.0), ["r"])


class ScaleTest(unittest.TestCase):
    def test_many_renews_keep_heap_tiny(self):
        wheel = ExpiryWheel(tick=1.0)
        wheel.add("hot", 1.0)
        for _ in range(10000):
            wheel.discard("hot", 1.0)
            wheel.add("hot", 1.0)
        self.assertLessEqual(len(wheel._nonempty), 1)
        self.assertEqual(wheel.pop_due(1.0), ["hot"])

    def test_sweep_cost_unrelated_to_active_total(self):
        def run(active):
            wheel = ExpiryWheel(tick=1.0)
            for index in range(active):
                wheel.add("alive-%05d" % index, 3600.0)
            for index in range(20):
                wheel.add("dead-%02d" % index, 1.0)
            start = time.perf_counter()
            dead = wheel.pop_due(1.0)
            return time.perf_counter() - start, dead

        small_t, small_dead = run(2000)
        large_t, large_dead = run(40000)
        self.assertEqual(len(small_dead), 20)
        self.assertEqual(len(large_dead), 20)
        # 翻倍活跃规模不拖垮只收 20 条的巡检（给足调度余量）。
        self.assertLess(large_t, small_t * 10 + 0.05)


if __name__ == "__main__":
    unittest.main()
