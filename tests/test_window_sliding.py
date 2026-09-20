"""SlidingWindow 修正后的真正“滑动”语义测试（基线仍在 test_window.py）。

旧实现一换桶就清空所有桶，滑窗名存实亡；这些测试锁住修正后的行为：
只清滑出窗口的老桶，其余桶继续计数。
"""

import unittest

from tracesamp import ManualClock, SlidingWindow


def make_window(window_seconds=1.0, buckets=4):
    clock = ManualClock()
    return SlidingWindow(window_seconds, buckets, clock), clock


class TestSlidingSemantics(unittest.TestCase):
    def test_data_survives_a_bucket_rotation_within_window(self):
        window, clock = make_window()
        window.add("total", 10)          # t=0，桶 0
        clock.advance(0.3)
        window.add("total", 5)           # t=0.3，桶 1
        # 已经滚过一个桶格，桶 0 的数据必须还在窗口里
        self.assertEqual(window.count("total"), 15)

    def test_only_the_stale_bucket_is_cleared(self):
        window, clock = make_window()
        window.add("total", 10)          # 桶 0
        clock.advance(0.3)
        window.add("total", 5)           # 桶 1
        clock.advance(0.3)               # t=0.6，桶 2
        window.add("total", 2)           # 桶 2
        self.assertEqual(window.count("total"), 17)
        clock.advance(0.5)               # t=1.1，桶 4：桶 0 过期
        self.assertEqual(window.count("total"), 7)

    def test_data_expires_one_window_after_arrival(self):
        window, clock = make_window()
        window.add("total", 10)
        clock.advance(0.9)
        self.assertEqual(window.count("total"), 10)
        clock.advance(0.2)               # 跨过 1 秒边界
        self.assertEqual(window.count("total"), 0)

    def test_multiple_rotations_keep_window_fresh(self):
        window, clock = make_window()
        window.add("total", 100)
        for _ in range(10):
            clock.advance(0.3)
            window.add("total", 1)
        # 早期的 100 早就过期，最近的写入也不超过窗口内写入总量
        count = window.count("total")
        self.assertLessEqual(count, 4)
        self.assertGreater(count, 0)


class TestSnapshot(unittest.TestCase):
    def test_snapshot_reads_keys_from_one_window_state(self):
        window, _ = make_window()
        window.add("total", 7)
        window.add("sampled", 3)
        snap = window.snapshot(("total", "sampled", "missing"))
        self.assertEqual(snap, {"total": 7, "sampled": 3, "missing": 0})

    def test_add_many_lands_in_one_bucket(self):
        window, clock = make_window()
        window.add_many({"total": 11, "sampled": 4})
        clock.advance(0.3)
        snap = window.snapshot(("total", "sampled"))
        self.assertEqual(snap, {"total": 11, "sampled": 4})

    def test_add_many_empty_is_a_noop(self):
        window, _ = make_window()
        window.add_many({})
        self.assertEqual(window.count("total"), 0)


if __name__ == "__main__":
    unittest.main()
