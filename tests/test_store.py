"""IdempotencyStore 现有行为的锁定测试。"""

import json
import os
import tempfile
import unittest

from idemkey import IdempotencyStore


class FakeClock:
    """手动推进的时钟。"""

    def __init__(self, start=1000.0):
        self.now = float(start)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class TestBeginFinishGet(unittest.TestCase):
    def test_begin_new_key_returns_true(self):
        store = IdempotencyStore()
        self.assertTrue(store.begin("order-1"))

    def test_get_unknown_key_returns_none(self):
        store = IdempotencyStore()
        self.assertIsNone(store.get("nope"))

    def test_finish_then_get_returns_result(self):
        store = IdempotencyStore()
        store.begin("order-1")
        store.finish("order-1", {"amount": 100, "state": "paid"})
        self.assertEqual(store.get("order-1"), {"amount": 100, "state": "paid"})

    def test_begin_after_finish_returns_false(self):
        store = IdempotencyStore()
        store.begin("order-1")
        store.finish("order-1", 7)
        self.assertFalse(store.begin("order-1"))

    def test_finish_without_begin_stores_result(self):
        store = IdempotencyStore()
        store.finish("solo", 42)
        self.assertEqual(store.get("solo"), 42)
        self.assertFalse(store.begin("solo"))

    def test_finish_overwrites_previous_result(self):
        store = IdempotencyStore()
        store.finish("order-1", "first")
        store.finish("order-1", "second")
        self.assertEqual(store.get("order-1"), "second")

    def test_distinct_keys_are_independent(self):
        store = IdempotencyStore()
        store.finish("a", 1)
        store.finish("b", 2)
        self.assertEqual(store.get("a"), 1)
        self.assertEqual(store.get("b"), 2)
        self.assertTrue(store.begin("c"))

    def test_whitespace_is_trimmed(self):
        store = IdempotencyStore()
        store.finish(" order-1 ", 5)
        self.assertEqual(store.get("order-1"), 5)

    def test_clock_is_injectable(self):
        store = IdempotencyStore(clock=lambda: 123.0)
        store.begin("k")
        store.finish("k", 1)
        self.assertEqual(store.get("k"), 1)


class TestExpiry(unittest.TestCase):
    def test_result_survives_until_ttl(self):
        clock = FakeClock()
        store = IdempotencyStore(ttl=60, clock=clock)
        store.begin("order-1")
        store.finish("order-1", "receipt")
        clock.advance(30)
        self.assertEqual(store.get("order-1"), "receipt")

    def test_result_expires_after_ttl(self):
        clock = FakeClock()
        store = IdempotencyStore(ttl=60, clock=clock)
        store.begin("order-1")
        store.finish("order-1", "receipt")
        clock.advance(61)
        self.assertIsNone(store.get("order-1"))

    def test_expired_key_can_be_processed_again(self):
        clock = FakeClock()
        store = IdempotencyStore(ttl=60, clock=clock)
        store.begin("order-1")
        store.finish("order-1", "first")
        clock.advance(61)
        self.assertTrue(store.begin("order-1"))
        store.finish("order-1", "second")
        self.assertEqual(store.get("order-1"), "second")

    def test_ttl_none_never_expires(self):
        clock = FakeClock()
        store = IdempotencyStore(ttl=None, clock=clock)
        store.begin("order-1")
        store.finish("order-1", "receipt")
        clock.advance(10 ** 6)
        self.assertEqual(store.get("order-1"), "receipt")
        self.assertFalse(store.begin("order-1"))

    def test_invalid_ttl_raises(self):
        with self.assertRaises(ValueError):
            IdempotencyStore(ttl=0)


class TestPersistence(unittest.TestCase):
    def test_records_are_written_to_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "idem.json")
            store = IdempotencyStore(path=path)
            store.begin("order-1")
            store.finish("order-1", {"amount": 100})
            self.assertTrue(os.path.exists(path))
            with open(path, "r", encoding="utf-8") as fh:
                self.assertIn("order-1", json.load(fh))

    def test_round_trip_within_one_instance(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "idem.json")
            store = IdempotencyStore(path=path)
            store.begin("order-1")
            store.finish("order-1", "receipt")
            self.assertEqual(store.get("order-1"), "receipt")
            self.assertFalse(store.begin("order-1"))


if __name__ == "__main__":
    unittest.main()
