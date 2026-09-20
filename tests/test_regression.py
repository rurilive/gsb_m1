"""对账异常的防回归测试。

对应生产上出现过的四类怪账，任何一项回潮都会让交易重复扣款或重发被误杀：

1. 超时重试下游多记一笔（重试把幂等键改成了 ``key#attempt``）
2. 重试耗尽后同键立刻重发被判重复（失败键被幂等窗口占住不放）
3. 成功半分钟后同键再发被挡、回执丢失（结果缓存 TTL 与幂等窗口不一致）
4. 配三次尝试只打出去两次（尝试次数 off-by-one）
"""

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


class RetryKeyTest(unittest.TestCase):
    def test_every_attempt_uses_same_idempotency_key(self):
        rec = Recorder([TransientError("timeout"), None])
        client = IdempotentClient(rec, clock=Clock(), ttl=60.0, max_attempts=3)
        receipt = client.submit("order-1", "扣款 100")
        self.assertEqual(len(rec.seen), 2)
        self.assertEqual({call_key for call_key, _ in rec.seen}, {"order-1"})
        self.assertEqual([call_key for call_key, _ in client.calls],
                         ["order-1", "order-1"])
        self.assertEqual(receipt.attempts, 2)
        self.assertFalse(receipt.replayed)

    def test_downstream_dedup_keys_never_carry_attempt_suffix(self):
        rec = Recorder([TransientError("a"), TransientError("b"), None])
        client = IdempotentClient(rec, clock=Clock(), max_attempts=3)
        client.submit("order-2", "扣款 200")
        self.assertTrue(
            all("#" not in call_key for call_key, _ in rec.seen),
            "重试键不得拼接尝试序号，否则下游按提交键去重会失效")


class AttemptBudgetTest(unittest.TestCase):
    def test_three_attempts_makes_three_calls(self):
        rec = Recorder([TransientError("a"), TransientError("b"),
                        TransientError("c")])
        client = IdempotentClient(rec, clock=Clock(), max_attempts=3)
        with self.assertRaises(RetryExhausted):
            client.submit("k-budget", "p")
        self.assertEqual(len(rec.seen), 3)

    def test_single_attempt_makes_one_call(self):
        rec = Recorder([TransientError("a")])
        client = IdempotentClient(rec, clock=Clock(), max_attempts=1)
        with self.assertRaises(RetryExhausted):
            client.submit("k-one", "p")
        self.assertEqual(len(rec.seen), 1)

    def test_success_on_third_attempt_reports_three(self):
        rec = Recorder([TransientError("a"), TransientError("b"), None])
        client = IdempotentClient(rec, clock=Clock(), max_attempts=3)
        self.assertEqual(client.submit("k-lucky3", "p").attempts, 3)
        self.assertEqual(len(rec.seen), 3)


class KeyReleaseOnFailureTest(unittest.TestCase):
    def test_resubmit_immediately_after_exhaustion_succeeds(self):
        rec = Recorder([TransientError("a"), TransientError("b"),
                        TransientError("c")])
        client = IdempotentClient(rec, clock=Clock(), ttl=60.0, max_attempts=3)
        with self.assertRaises(RetryExhausted):
            client.submit("order-3", "扣款 300")
        receipt = client.submit("order-3", "扣款 300")
        self.assertFalse(receipt.replayed)
        self.assertEqual(len(rec.seen), 4)

    def test_resubmit_within_window_after_exhaustion_not_duplicate(self):
        clock = Clock()
        rec = Recorder([TransientError("a"), TransientError("b"),
                        TransientError("c"), None])
        client = IdempotentClient(rec, clock=clock, ttl=60.0, max_attempts=3)
        with self.assertRaises(RetryExhausted):
            client.submit("order-4", "p")
        clock.advance(30.0)
        try:
            receipt = client.submit("order-4", "p")
        except DuplicateKey:
            self.fail("失败键不该占住幂等窗口，恢复后应允许立刻重发")
        self.assertFalse(receipt.replayed)

    def test_permanent_failure_releases_key(self):
        rec = Recorder([PermanentError("bad"), None])
        client = IdempotentClient(rec, clock=Clock(), ttl=60.0)
        with self.assertRaises(PermanentError):
            client.submit("order-5", "p")
        receipt = client.submit("order-5", "p")
        self.assertFalse(receipt.replayed)
        self.assertEqual(len(rec.seen), 2)


class ResultTtlAlignmentTest(unittest.TestCase):
    def test_replay_still_available_at_thirty_seconds(self):
        clock = Clock()
        rec = Recorder()
        client = IdempotentClient(rec, clock=clock, ttl=60.0)
        client.submit("order-6", "扣款 600")
        clock.advance(30.0)
        receipt = client.submit("order-6", "扣款 600")
        self.assertTrue(receipt.replayed)
        self.assertEqual(len(rec.seen), 1)

    def test_replay_available_until_end_of_idempotency_window(self):
        clock = Clock()
        rec = Recorder()
        client = IdempotentClient(rec, clock=clock, ttl=60.0)
        client.submit("order-7", "p")
        clock.advance(59.0)
        self.assertTrue(client.submit("order-7", "p").replayed)
        self.assertEqual(len(rec.seen), 1)
        clock.advance(2.0)
        self.assertFalse(client.submit("order-7", "p").replayed)
        self.assertEqual(len(rec.seen), 2)

    def test_inflight_same_key_is_still_rejected(self):
        case = self

        class BlockingTransport:
            def __call__(self, key, payload):
                with case.assertRaises(DuplicateKey):
                    client.submit(key, payload)
                return {"payload": payload}

        client = IdempotentClient(BlockingTransport(), clock=Clock(), ttl=60.0)
        receipt = client.submit("order-8", "p")
        self.assertFalse(receipt.replayed)


if __name__ == "__main__":
    unittest.main()
