"""基线测试：锁住 SimpleTimer 的现状行为，必须全绿，一字不许改。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from timewheel import SimpleTimer, TimerError


class TestAddAndPeek(unittest.TestCase):
    def test_new_timer_is_empty(self):
        t = SimpleTimer()
        self.assertEqual(t.now, 0)
        self.assertEqual(t.size, 0)
        self.assertIsNone(t.peek())

    def test_add_at_sets_due_and_size(self):
        t = SimpleTimer()
        t.add_at(3, "a")
        t.add_at(5, "b")
        self.assertEqual(t.size, 2)
        self.assertEqual(t.peek(), 3)

    def test_zero_delay_peeks_now(self):
        t = SimpleTimer()
        t.add_at(0, "z")
        self.assertEqual(t.peek(), 0)

    def test_peek_returns_min_due(self):
        t = SimpleTimer()
        t.add_at(9, "late")
        t.add_at(4, "early")
        t.add_at(6, "mid")
        self.assertEqual(t.peek(), 4)


class TestAdvance(unittest.TestCase):
    def test_fires_in_due_then_insertion_order(self):
        t = SimpleTimer()
        t.add_at(2, "a")
        t.add_at(1, "b")
        t.add_at(2, "c")
        self.assertEqual(t.advance(2), ["b", "a", "c"])
        self.assertEqual(t.size, 0)

    def test_same_tick_multiple_fire_by_insertion(self):
        t = SimpleTimer()
        t.add_at(1, "x")
        t.add_at(1, "y")
        t.add_at(1, "z")
        self.assertEqual(t.advance(1), ["x", "y", "z"])

    def test_advance_zero_returns_empty(self):
        t = SimpleTimer()
        t.add_at(1, "a")
        self.assertEqual(t.advance(0), [])
        self.assertEqual(t.now, 0)
        self.assertEqual(t.size, 1)

    def test_advance_steps_clock(self):
        t = SimpleTimer()
        t.add_at(5, "a")
        self.assertEqual(t.advance(3), [])
        self.assertEqual(t.now, 3)
        self.assertEqual(t.advance(2), ["a"])
        self.assertEqual(t.now, 5)

    def test_fire_once_not_repeated(self):
        t = SimpleTimer()
        t.add_at(1, "a")
        self.assertEqual(t.advance(1), ["a"])
        self.assertEqual(t.advance(1), [])
        self.assertEqual(t.size, 0)

    def test_negative_advance_fails_fast(self):
        t = SimpleTimer()
        with self.assertRaises(TimerError):
            t.advance(-1)

    def test_non_int_advance_fails_fast(self):
        t = SimpleTimer()
        with self.assertRaises(TimerError):
            t.advance(1.5)


class TestCancel(unittest.TestCase):
    def test_cancel_removes_pending(self):
        t = SimpleTimer()
        t.add_at(3, "a")
        t.add_at(4, "b")
        self.assertTrue(t.cancel("a"))
        self.assertEqual(t.size, 1)
        self.assertEqual(t.advance(4), ["b"])

    def test_cancel_missing_returns_false(self):
        t = SimpleTimer()
        self.assertFalse(t.cancel("nope"))

    def test_cancel_does_not_remove_other(self):
        t = SimpleTimer()
        t.add_at(2, "a")
        self.assertFalse(t.cancel("b"))
        self.assertEqual(t.size, 1)


class TestErrors(unittest.TestCase):
    def test_negative_delay_fails_fast(self):
        t = SimpleTimer()
        with self.assertRaises(TimerError):
            t.add_at(-1, "a")

    def test_timer_error_is_value_error(self):
        self.assertTrue(issubclass(TimerError, ValueError))

    def test_non_int_delay_fails_fast(self):
        t = SimpleTimer()
        with self.assertRaises(TimerError):
            t.add_at(1.5, "a")


if __name__ == "__main__":
    unittest.main()
