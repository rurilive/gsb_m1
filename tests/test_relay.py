"""可靠中继的行为测试：退避、死信、租约与聚合键保序。"""

import unittest

from outboxd.outbox import MemoryStore, Outbox


class FakeClock:
    """可手动推进的假时钟，relay 不真 sleep，全靠它验证退避时刻。"""

    def __init__(self, now=0.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, dt):
        self.now += dt


class FlakySender:
    """按 seq 记录投递时刻的假 sender，可指定哪些 seq 一直失败。"""

    def __init__(self, clock, fail_on=()):
        self._clock = clock
        self._fail_on = set(fail_on)
        self.attempts = []

    def send(self, row):
        self.attempts.append((row["seq"], self._clock()))
        if row["seq"] in self._fail_on:
            raise RuntimeError("boom %s" % row["seq"])


class TestBackoff(unittest.TestCase):
    def test_retry_waits_until_backoff_elapses(self):
        clock = FakeClock()
        store = MemoryStore()
        sender = FlakySender(clock, fail_on=[1])
        box = Outbox(store, sender, clock=clock, base_backoff=2.0)
        box.record("a", "x", {})

        box.relay()
        self.assertEqual(sender.attempts, [(1, 0.0)])
        self.assertEqual(store.get(1)["next_attempt_at"], 2.0)

        box.relay()
        clock.advance(1.9)
        box.relay()
        self.assertEqual(len(sender.attempts), 1)

        clock.advance(0.1)
        box.relay()
        self.assertEqual(sender.attempts, [(1, 0.0), (1, 2.0)])

    def test_backoff_grows_exponentially(self):
        clock = FakeClock()
        store = MemoryStore()
        sender = FlakySender(clock, fail_on=[1])
        box = Outbox(store, sender, clock=clock, base_backoff=1.0)
        box.record("a", "x", {})

        for _ in range(4):
            box.relay()
            clock.advance(store.get(1)["next_attempt_at"] - clock.now)
        self.assertEqual([t for _, t in sender.attempts], [0.0, 1.0, 3.0, 7.0])

    def test_sent_row_is_not_revisited(self):
        clock = FakeClock()
        store = MemoryStore()
        sender = FlakySender(clock)
        box = Outbox(store, sender, clock=clock)
        box.record("a", "x", {})
        box.relay()
        clock.advance(1000.0)
        self.assertEqual(box.relay(), 0)
        self.assertEqual(len(sender.attempts), 1)


class TestDeadLetter(unittest.TestCase):
    def test_moves_to_dead_after_max_attempts(self):
        clock = FakeClock()
        store = MemoryStore()
        sender = FlakySender(clock, fail_on=[1])
        box = Outbox(store, sender, clock=clock,
                     max_attempts=3, base_backoff=1.0)
        box.record("a", "x", {})

        for _ in range(2):
            box.relay()
            self.assertEqual(store.get(1)["status"], "pending")
            clock.advance(store.get(1)["next_attempt_at"] - clock.now)
        box.relay()
        self.assertEqual(store.get(1)["status"], "dead")
        self.assertEqual(len(sender.attempts), 3)

        clock.advance(1000.0)
        box.relay()
        self.assertEqual(len(sender.attempts), 3)

    def test_dead_head_unblocks_following_rows(self):
        clock = FakeClock()
        store = MemoryStore()
        sender = FlakySender(clock, fail_on=[1])
        box = Outbox(store, sender, clock=clock,
                     max_attempts=2, base_backoff=1.0)
        box.record("a", "x", {"n": 1})
        box.record("a", "y", {"n": 2})

        box.relay()
        self.assertEqual([s for s, _ in sender.attempts], [1])
        clock.advance(store.get(1)["next_attempt_at"] - clock.now)
        box.relay()
        self.assertEqual(store.get(1)["status"], "dead")
        self.assertEqual(store.get(2)["status"], "sent")
        self.assertEqual([s for s, _ in sender.attempts], [1, 1, 2])


class TestOrdering(unittest.TestCase):
    def test_failed_head_blocks_same_aggregate_only(self):
        clock = FakeClock()
        store = MemoryStore()
        sender = FlakySender(clock, fail_on=[1])
        box = Outbox(store, sender, clock=clock)
        box.record("a", "x", {"n": 1})
        box.record("a", "y", {"n": 2})
        box.record("b", "z", {"n": 3})

        self.assertEqual(box.relay(), 1)
        self.assertEqual([s for s, _ in sender.attempts], [1, 3])
        self.assertEqual(store.get(2)["status"], "pending")

    def test_redelivery_follows_record_order(self):
        clock = FakeClock()
        store = MemoryStore()
        sender = FlakySender(clock, fail_on=[1])
        box = Outbox(store, sender, clock=clock)
        box.record("a", "x", {"n": 1})
        box.record("a", "y", {"n": 2})

        box.relay()
        sender._fail_on.clear()
        clock.advance(store.get(1)["next_attempt_at"] - clock.now)
        self.assertEqual(box.relay(), 2)
        self.assertEqual([s for s, _ in sender.attempts], [1, 1, 2])


class TestLease(unittest.TestCase):
    def test_concurrent_relay_skips_leased_row(self):
        clock = FakeClock()
        store = MemoryStore()
        inner_delivered = []

        class ReentrantSender:
            def send(self, row):
                other = Outbox(store, FlakySender(clock), clock=clock,
                               owner="other")
                inner_delivered.append(other.relay())

        box = Outbox(store, ReentrantSender(), clock=clock, owner="main")
        box.record("a", "x", {})
        self.assertEqual(box.relay(), 1)
        self.assertEqual(inner_delivered, [0])
        self.assertEqual(store.get(1)["status"], "sent")

    def test_lease_is_mutually_exclusive_until_expiry(self):
        store = MemoryStore()
        box = Outbox(store, FlakySender(FakeClock()))
        seq = box.record("a", "x", {})

        self.assertTrue(store.claim(seq, "one", now=10.0, ttl=5.0))
        self.assertFalse(store.claim(seq, "two", now=12.0, ttl=5.0))
        self.assertTrue(store.claim(seq, "one", now=12.0, ttl=5.0))
        self.assertFalse(store.claim(seq, "two", now=15.0, ttl=5.0))
        self.assertTrue(store.claim(seq, "two", now=17.0, ttl=5.0))
        store.release(seq, "two")
        self.assertTrue(store.claim(seq, "three", now=17.0, ttl=5.0))


if __name__ == "__main__":
    unittest.main()
