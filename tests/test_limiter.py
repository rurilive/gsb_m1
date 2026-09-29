"""Tests that lock down the baseline CounterLimiter behaviour.

These tests describe the shipped, naive semantics: a single cumulative counter
that never recovers. They must keep passing unchanged after the sliding window
work is done.
"""

import unittest

from flowcap import CounterLimiter, FlowError


class CounterLimiterTest(unittest.TestCase):
    def test_allows_up_to_limit(self):
        limiter = CounterLimiter(limit=3)
        self.assertTrue(limiter.allow())
        self.assertTrue(limiter.allow())
        self.assertTrue(limiter.allow())
        self.assertFalse(limiter.allow())
        self.assertFalse(limiter.allow())

    def test_counter_grows_even_on_reject(self):
        limiter = CounterLimiter(limit=1)
        self.assertTrue(limiter.allow())
        self.assertFalse(limiter.allow())
        self.assertFalse(limiter.allow())
        self.assertEqual(limiter.count, 3)

    def test_limit_property(self):
        limiter = CounterLimiter(limit=5)
        self.assertEqual(limiter.limit, 5)

    def test_zero_limit_rejects_everything(self):
        limiter = CounterLimiter(limit=0)
        self.assertFalse(limiter.allow())

    def test_negative_limit_is_rejected(self):
        with self.assertRaises(FlowError):
            CounterLimiter(limit=-1)

    def test_non_int_limit_is_rejected(self):
        with self.assertRaises(FlowError):
            CounterLimiter(limit=1.5)

    def test_flow_error_is_exception(self):
        self.assertTrue(issubclass(FlowError, Exception))


if __name__ == "__main__":
    unittest.main()
