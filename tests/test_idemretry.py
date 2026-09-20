"""idemretry 行为基线：锁住对外契约，修复过程中必须一直全绿。"""

import unittest

from idemretry import (
    IdempotentClient,
    PermanentError,
    Receipt,
    RetryExhausted,
    TransientError,
)


class Clock:
    """可手动推进的时钟。"""

    def __init__(self, now=0.0):
        self.now = float(now)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += float(seconds)


class Recorder:
    """假下游：记录收到的调用，按脚本抛错；脚本里的 None 表示这一次成功。"""

    def __init__(self, script=None):
        self.seen = []
        self.script = list(script or [])

    def __call__(self, key, payload):
        self.seen.append((key, payload))
        if self.script:
            step = self.script.pop(0)
            if step is not None:
                raise step
        return {"payload": payload}


class FirstSubmitTest(unittest.TestCase):
    def test_executes_transport_once(self):
        rec = Recorder()
        client = IdempotentClient(rec, clock=Clock(), ttl=60.0)
        receipt = client.submit("k1", "p1")
        self.assertIsInstance(receipt, Receipt)
        self.assertEqual(receipt.value, {"payload": "p1"})
        self.assertEqual(len(rec.seen), 1)
        self.assertFalse(receipt.replayed)

    def test_attempts_reports_one(self):
        client = IdempotentClient(Recorder(), clock=Clock(), ttl=60.0)
        self.assertEqual(client.submit("k2", "p2").attempts, 1)


class IdempotentReplayTest(unittest.TestCase):
    def test_same_key_replays_without_executing(self):
        rec = Recorder()
        client = IdempotentClient(rec, clock=Clock(), ttl=60.0)
        first = client.submit("k3", "p3")
        second = client.submit("k3", "p3")
        self.assertEqual(second.value, first.value)
        self.assertTrue(second.replayed)
        self.assertEqual(len(rec.seen), 1)

    def test_replay_within_window(self):
        clock = Clock()
        rec = Recorder()
        client = IdempotentClient(rec, clock=clock, ttl=60.0)
        client.submit("k4", "p4")
        clock.advance(5.0)
        self.assertTrue(client.submit("k4", "p4").replayed)

    def test_different_keys_both_execute(self):
        rec = Recorder()
        client = IdempotentClient(rec, clock=Clock(), ttl=60.0)
        client.submit("k5a", "p5")
        client.submit("k5b", "p5")
        self.assertEqual(len(rec.seen), 2)

    def test_after_ttl_key_can_be_reused(self):
        clock = Clock()
        rec = Recorder()
        client = IdempotentClient(rec, clock=clock, ttl=60.0)
        client.submit("k6", "p6")
        clock.advance(61.0)
        receipt = client.submit("k6", "p6")
        self.assertFalse(receipt.replayed)
        self.assertEqual(len(rec.seen), 2)


class RetryTest(unittest.TestCase):
    def test_transient_then_success(self):
        rec = Recorder([TransientError("boom"), None])
        client = IdempotentClient(rec, clock=Clock(), ttl=60.0, max_attempts=3)
        receipt = client.submit("k7", "p7")
        self.assertEqual(receipt.value, {"payload": "p7"})
        self.assertEqual(receipt.attempts, 2)
        self.assertEqual(len(rec.seen), 2)
        self.assertFalse(receipt.replayed)

    def test_permanent_error_not_retried(self):
        rec = Recorder([PermanentError("bad")])
        client = IdempotentClient(rec, clock=Clock(), ttl=60.0, max_attempts=3)
        with self.assertRaises(PermanentError):
            client.submit("k8", "p8")
        self.assertEqual(len(rec.seen), 1)

    def test_exhausted_retries_raise(self):
        rec = Recorder([TransientError("a"), TransientError("b"), TransientError("c")])
        client = IdempotentClient(rec, clock=Clock(), ttl=60.0, max_attempts=3)
        with self.assertRaises(RetryExhausted):
            client.submit("k9", "p9")


if __name__ == "__main__":
    unittest.main()
