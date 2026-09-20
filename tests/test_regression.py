"""idemretry 对账事故回归测试：锁住四类已修复现象的根因。"""

import unittest

from idemretry import (
    DuplicateKey,
    IdempotentClient,
    PermanentError,
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


class RetryKeepsIdempotencyKeyTest(unittest.TestCase):
    """重试必须带原始幂等键，否则下游按提交键去重会失效、重复扣款。"""

    def test_retries_send_the_same_key(self):
        rec = Recorder([TransientError("boom"), None])
        client = IdempotentClient(rec, clock=Clock(), ttl=60.0, max_attempts=3)
        client.submit("order-1", "扣款 100")
        self.assertEqual([key for key, _ in rec.seen], ["order-1", "order-1"])

    def test_calls_log_matches_transport_keys(self):
        rec = Recorder([TransientError("boom"), None])
        client = IdempotentClient(rec, clock=Clock(), ttl=60.0, max_attempts=3)
        client.submit("order-2", "扣款 100")
        self.assertEqual(client.calls, rec.seen)


class FullAttemptBudgetTest(unittest.TestCase):
    """max_attempts 次尝试（含首次）必须打满，不能差一。"""

    def test_uses_all_configured_attempts(self):
        rec = Recorder([TransientError("a"), TransientError("b"), None])
        client = IdempotentClient(rec, clock=Clock(), ttl=60.0, max_attempts=3)
        receipt = client.submit("k1", "p1")
        self.assertEqual(receipt.attempts, 3)
        self.assertEqual(len(rec.seen), 3)

    def test_exhaustion_after_exactly_max_attempts(self):
        rec = Recorder([TransientError("x")] * 10)
        client = IdempotentClient(rec, clock=Clock(), ttl=60.0, max_attempts=3)
        with self.assertRaises(RetryExhausted):
            client.submit("k2", "p2")
        self.assertEqual(len(rec.seen), 3)


class FailedSubmitReleasesKeyTest(unittest.TestCase):
    """未成功的提交不占键：同键重发应被重新受理，而不是 DuplicateKey。"""

    def test_resubmit_after_retry_exhausted(self):
        clock = Clock()
        rec = Recorder([TransientError("a"), TransientError("b"), TransientError("c"), None])
        client = IdempotentClient(rec, clock=clock, ttl=60.0, max_attempts=3)
        with self.assertRaises(RetryExhausted):
            client.submit("k3", "p3")
        clock.advance(1.0)
        receipt = client.submit("k3", "p3")
        self.assertFalse(receipt.replayed)
        self.assertEqual(receipt.value, {"payload": "p3"})

    def test_resubmit_after_permanent_error(self):
        rec = Recorder([PermanentError("bad"), None])
        client = IdempotentClient(rec, clock=Clock(), ttl=60.0, max_attempts=3)
        with self.assertRaises(PermanentError):
            client.submit("k4", "p4")
        receipt = client.submit("k4", "p4")
        self.assertFalse(receipt.replayed)


class ReplayForWholeWindowTest(unittest.TestCase):
    """结果缓存与幂等窗口同寿命：窗口内同键提交永远回放回执。"""

    def test_replay_after_result_would_have_expired(self):
        clock = Clock()
        rec = Recorder()
        client = IdempotentClient(rec, clock=clock, ttl=60.0)
        first = client.submit("k5", "p5")
        clock.advance(31.0)  # 越过旧的 30 秒结果缓存期，但仍在幂等窗口内
        second = client.submit("k5", "p5")
        self.assertTrue(second.replayed)
        self.assertEqual(second.value, first.value)
        self.assertEqual(len(rec.seen), 1)

    def test_no_duplicate_key_within_window(self):
        clock = Clock()
        rec = Recorder()
        client = IdempotentClient(rec, clock=clock, ttl=60.0)
        client.submit("k6", "p6")
        clock.advance(45.0)
        try:
            client.submit("k6", "p6")
        except DuplicateKey:
            self.fail("窗口内同键提交应回放回执，不应抛 DuplicateKey")


if __name__ == "__main__":
    unittest.main()
