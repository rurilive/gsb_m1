"""TimerSet 现有行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from tickbox.timers import TimerSet


class FakeClock:
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


class TestTimerSet(unittest.TestCase):
    def test_add_and_fire(self):
        c = FakeClock()
        t = TimerSet(clock=c)
        t.add(5, payload="a")
        t.add(10, payload="b")
        due = t.tick(5)
        self.assertEqual([h.payload for h in due], ["a"])
        self.assertEqual(t.size, 1)
        due = t.tick(10)
        self.assertEqual([h.payload for h in due], ["b"])

    def test_nothing_due(self):
        c = FakeClock()
        t = TimerSet(clock=c)
        t.add(10, payload="x")
        self.assertEqual(t.tick(9), [])
        self.assertEqual(t.size, 1)

    def test_cancel_prevents_fire(self):
        c = FakeClock()
        t = TimerSet(clock=c)
        h = t.add(5, payload="x")
        self.assertTrue(h.cancel())
        self.assertEqual(t.tick(5), [])
        self.assertTrue(h.cancelled)

    def test_double_cancel_returns_false(self):
        c = FakeClock()
        t = TimerSet(clock=c)
        h = t.add(5, payload="x")
        self.assertTrue(h.cancel())
        self.assertFalse(h.cancel())

    def test_deadline_equal_to_now_fires(self):
        c = FakeClock()
        t = TimerSet(clock=c)
        t.add(5, payload="x")
        due = t.tick(5)
        self.assertEqual(len(due), 1)

    def test_multiple_due_sorted_by_deadline(self):
        c = FakeClock()
        t = TimerSet(clock=c)
        t.add(9, payload="late")
        t.add(3, payload="early")
        t.add(6, payload="mid")
        due = t.tick(10)
        self.assertEqual([h.payload for h in due], ["early", "mid", "late"])

    def test_same_deadline_keeps_insertion_order(self):
        c = FakeClock()
        t = TimerSet(clock=c)
        t.add(4, payload="first")
        t.add(4, payload="second")
        t.add(4, payload="third")
        due = t.tick(4)
        self.assertEqual([h.payload for h in due], ["first", "second", "third"])

    def test_backwards_clock_rejected(self):
        c = FakeClock()
        t = TimerSet(clock=c)
        with self.assertRaises(ValueError):
            t.tick(-1)

    def test_nonpositive_delay_rejected(self):
        c = FakeClock()
        t = TimerSet(clock=c)
        with self.assertRaises(ValueError):
            t.add(0)
        with self.assertRaises(ValueError):
            t.add(-3)


if __name__ == "__main__":
    unittest.main()
