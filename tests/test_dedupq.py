"""dedupq 行为基线：锁住对外契约，修复过程中必须一直全绿。"""

import unittest

from dedupq import DedupQueue, FakeClock


class SubmitDedupTest(unittest.TestCase):
    def test_new_id_accepted(self):
        q = DedupQueue(ttl=60.0, clock=FakeClock(0.0))
        self.assertTrue(q.submit("a-new", {"n": 1}))
        self.assertEqual(q.size(), 1)

    def test_duplicate_id_rejected(self):
        q = DedupQueue(ttl=60.0, clock=FakeClock(0.0))
        self.assertTrue(q.submit("b-dup", {"n": 1}))
        self.assertFalse(q.submit("b-dup", {"n": 2}))
        self.assertEqual(q.size(), 1)

    def test_duplicate_keeps_first_payload(self):
        q = DedupQueue(ttl=60.0, clock=FakeClock(0.0))
        q.submit("b-keep", {"n": "first"})
        q.submit("b-keep", {"n": "second"})
        self.assertEqual(q.pop(), ("b-keep", {"n": "first"}))


class FifoOrderTest(unittest.TestCase):
    def test_pop_returns_fifo(self):
        q = DedupQueue(ttl=60.0, clock=FakeClock(0.0))
        for mid in ["c1", "c2", "c3"]:
            q.submit(mid, mid.upper())
        self.assertEqual([q.pop() for _ in range(3)],
                         [("c1", "C1"), ("c2", "C2"), ("c3", "C3")])

    def test_pop_empty_returns_none(self):
        q = DedupQueue(ttl=60.0, clock=FakeClock(0.0))
        self.assertIsNone(q.pop())

    def test_peek_does_not_consume(self):
        q = DedupQueue(ttl=60.0, clock=FakeClock(0.0))
        q.submit("d1", {"n": 1})
        self.assertEqual(q.peek(), ("d1", {"n": 1}))
        self.assertEqual(q.size(), 1)
        self.assertEqual(q.pop(), ("d1", {"n": 1}))

    def test_peek_empty_returns_none(self):
        q = DedupQueue(ttl=60.0, clock=FakeClock(0.0))
        self.assertIsNone(q.peek())

    def test_len_matches_size(self):
        q = DedupQueue(ttl=60.0, clock=FakeClock(0.0))
        q.submit("g1", None)
        q.submit("g2", None)
        self.assertEqual(len(q), q.size())
        self.assertEqual(len(q), 2)


class TtlExpiryTest(unittest.TestCase):
    def test_same_id_reallowed_after_ttl(self):
        clock = FakeClock(0.0)
        q = DedupQueue(ttl=5.0, clock=clock)
        self.assertTrue(q.submit("e1", None))
        self.assertFalse(q.submit("e1", None))
        clock.advance(6.0)
        self.assertTrue(q.submit("e1", None))
        self.assertEqual(q.size(), 2)

    def test_cleanup_drops_expired_record(self):
        clock = FakeClock(0.0)
        q = DedupQueue(ttl=5.0, clock=clock)
        q.submit("f1", None)
        clock.advance(6.0)
        q.cleanup()
        self.assertTrue(q.submit("f1", None))

    def test_record_alive_before_ttl(self):
        clock = FakeClock(0.0)
        q = DedupQueue(ttl=5.0, clock=clock)
        q.submit("h1", None)
        clock.advance(4.9)
        q.cleanup()
        self.assertFalse(q.submit("h1", None))


class InstanceStateTest(unittest.TestCase):
    def test_fresh_queue_starts_empty(self):
        q = DedupQueue(ttl=60.0, clock=FakeClock(0.0))
        self.assertEqual(q.size(), 0)
        self.assertIsNone(q.pop())

    def test_payload_roundtrip(self):
        q = DedupQueue(ttl=60.0, clock=FakeClock(0.0))
        payload = {"body": "x", "tags": ["p", "q"]}
        q.submit("i1", payload)
        self.assertIs(q.peek()[1], payload)


if __name__ == "__main__":
    unittest.main()
