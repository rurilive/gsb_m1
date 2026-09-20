"""FixedWindowLimiter 现有行为的锁定测试。"""

import unittest

from shapeq.limiter import FixedWindowLimiter


class ManualClock:
    """可推进的假时钟，测试里精确控制窗口边界。"""

    def __init__(self, now=0.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class TestFixedWindowLimiter(unittest.TestCase):
    def test_allow_under_limit(self):
        lim = FixedWindowLimiter(limit=2, window=10.0)
        self.assertTrue(lim.allow("a"))
        self.assertTrue(lim.allow("a"))

    def test_reject_over_limit_counts(self):
        lim = FixedWindowLimiter(limit=2, window=10.0)
        lim.allow("a")
        lim.allow("a")
        self.assertFalse(lim.allow("a"))
        self.assertEqual(lim.stats()["rejected"], 1)
        self.assertEqual(lim.stats()["allowed"], 2)

    def test_keys_are_independent(self):
        lim = FixedWindowLimiter(limit=1, window=10.0)
        self.assertTrue(lim.allow("a"))
        self.assertFalse(lim.allow("a"))
        self.assertTrue(lim.allow("b"))
        self.assertEqual(lim.stats()["keys"], 2)

    def test_window_resets_on_clock_advance(self):
        clock = ManualClock()
        lim = FixedWindowLimiter(limit=1, window=10.0, clock=clock)
        self.assertTrue(lim.allow("a"))
        self.assertFalse(lim.allow("a"))
        clock.advance(10.0)          # 跨到下一个窗口
        self.assertTrue(lim.allow("a"))

    def test_window_boundary_is_exclusive_at_multiple(self):
        clock = ManualClock()
        lim = FixedWindowLimiter(limit=1, window=10.0, clock=clock)
        self.assertTrue(lim.allow("a"))
        clock.advance(9.999)         # 仍在同一窗口内
        self.assertFalse(lim.allow("a"))
        clock.advance(0.001)         # 恰好落在窗口边界上
        self.assertTrue(lim.allow("a"))

    def test_advancing_within_window_does_not_reset(self):
        clock = ManualClock()
        lim = FixedWindowLimiter(limit=2, window=10.0, clock=clock)
        lim.allow("a")
        clock.advance(3.0)
        self.assertTrue(lim.allow("a"))
        clock.advance(3.0)
        self.assertFalse(lim.allow("a"))

    def test_stats_returns_fresh_dict(self):
        lim = FixedWindowLimiter(limit=1, window=10.0)
        s = lim.stats()
        s["allowed"] = 99
        self.assertEqual(lim.stats()["allowed"], 0)

    def test_clock_is_injectable(self):
        lim = FixedWindowLimiter(limit=1, window=10.0, clock=lambda: 123.0)
        self.assertTrue(lim.allow("a"))

    def test_invalid_limit_raises(self):
        with self.assertRaises(ValueError):
            FixedWindowLimiter(limit=0, window=10.0)

    def test_invalid_window_raises(self):
        with self.assertRaises(ValueError):
            FixedWindowLimiter(limit=1, window=0.0)


if __name__ == "__main__":
    unittest.main()
