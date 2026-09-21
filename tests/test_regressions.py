"""对账事故与新增功能的防回归测试（合入前提，必须全绿）。"""

import json
import os
import tempfile
import unittest

from idemkey import IdempotencyStore, TruncatedResult


class FakeClock:
    """手动推进的时钟。"""

    def __init__(self, start=1000.0):
        self.now = float(start)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class TestCaseSensitiveKeys(unittest.TestCase):
    """事故 1：大小写不同的单号不得并成一笔。"""

    def test_case_variants_are_distinct_keys(self):
        store = IdempotencyStore()
        self.assertTrue(store.begin("Order-7001"))
        store.finish("Order-7001", {"order": "Order-7001", "amount": 100})

        self.assertTrue(store.begin("order-7001"))
        store.finish("order-7001", {"order": "order-7001", "amount": 200})

        self.assertEqual(store.get("Order-7001"),
                         {"order": "Order-7001", "amount": 100})
        self.assertEqual(store.get("order-7001"),
                         {"order": "order-7001", "amount": 200})

    def test_case_variants_distinct_across_persistence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "idem.json")
            before = IdempotencyStore(path=path)
            before.finish("Pay-A", "upper")
            before.finish("pay-a", "lower")

            after = IdempotencyStore(path=path)
            self.assertEqual(after.get("Pay-A"), "upper")
            self.assertEqual(after.get("pay-a"), "lower")
            self.assertFalse(after.begin("Pay-A"))
            self.assertFalse(after.begin("pay-a"))


class TestResultPersistedOnFinish(unittest.TestCase):
    """事故 2：finish 后结果必须落盘，重启后可回放、判重复。"""

    def test_result_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "idem.json")
            before = IdempotencyStore(path=path)
            before.begin("pay-88")
            before.finish("pay-88", {"amount": 250, "state": "paid"})

            with open(path, "r", encoding="utf-8") as fh:
                on_disk = json.load(fh)
            self.assertEqual(on_disk["pay-88"]["result"],
                             {"amount": 250, "state": "paid"})
            self.assertIsNotNone(on_disk["pay-88"]["finished_at"])

            after = IdempotencyStore(path=path)
            self.assertEqual(after.get("pay-88"),
                             {"amount": 250, "state": "paid"})
            self.assertFalse(after.begin("pay-88"))

    def test_purged_keys_are_removed_from_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "idem.json")
            clock = FakeClock()
            store = IdempotencyStore(ttl=60, clock=clock, path=path)
            store.begin("pay-1")
            store.finish("pay-1", "receipt")
            clock.advance(61)
            self.assertIsNone(store.get("pay-1"))

            with open(path, "r", encoding="utf-8") as fh:
                self.assertEqual(json.load(fh), {})


class TestMidwayFailureReleasesKey(unittest.TestCase):
    """事故 3：处理中途失败的残键不得卡死重发。"""

    def test_rebegin_after_failed_attempt(self):
        store = IdempotencyStore()
        self.assertTrue(store.begin("pay-99"))
        # 没有 finish：模拟下游超时、半途失败
        self.assertIsNone(store.get("pay-99"))
        self.assertTrue(store.begin("pay-99"))
        store.finish("pay-99", {"state": "paid"})
        self.assertEqual(store.get("pay-99"), {"state": "paid"})
        self.assertFalse(store.begin("pay-99"))

    def test_retry_flow_does_not_replay_empty_result(self):
        store = IdempotencyStore()
        attempts = {"n": 0}

        def do_work():
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise RuntimeError("下游超时")
            return {"state": "paid"}

        def submit():
            if not store.begin("pay-99"):
                return store.get("pay-99")
            result = do_work()
            store.finish("pay-99", result)
            return result

        with self.assertRaises(RuntimeError):
            submit()
        self.assertEqual(submit(), {"state": "paid"})
        self.assertEqual(store.get("pay-99"), {"state": "paid"})

    def test_inflight_placeholder_left_on_disk_does_not_block_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "idem.json")
            crashed = IdempotencyStore(path=path)
            crashed.begin("pay-99")  # 崩溃在 finish 之前

            restarted = IdempotencyStore(path=path)
            self.assertIsNone(restarted.get("pay-99"))
            self.assertTrue(restarted.begin("pay-99"))
            restarted.finish("pay-99", {"state": "paid"})
            self.assertEqual(restarted.get("pay-99"), {"state": "paid"})


class TestTtlFromFinishedAt(unittest.TestCase):
    """事故 4：有效期按完成时刻算，在途记录不参与过期。"""

    def test_result_immediately_after_long_processing_is_alive(self):
        clock = FakeClock()
        store = IdempotencyStore(ttl=60, clock=clock)
        store.begin("pay-77")
        clock.advance(90)
        store.finish("pay-77", {"amount": 300})
        self.assertEqual(store.get("pay-77"), {"amount": 300})

    def test_ttl_window_starts_at_finish(self):
        clock = FakeClock()
        store = IdempotencyStore(ttl=60, clock=clock)
        store.begin("pay-77")
        clock.advance(90)
        store.finish("pay-77", {"amount": 300})

        clock.advance(59)
        self.assertEqual(store.get("pay-77"), {"amount": 300})
        clock.advance(1)
        self.assertIsNone(store.get("pay-77"))
        self.assertTrue(store.begin("pay-77"))

    def test_inflight_record_is_never_purged(self):
        clock = FakeClock()
        store = IdempotencyStore(ttl=10, clock=clock)
        store.begin("slow")
        clock.advance(1000)
        # 在途期间别的键的操作触发 purge，也不能把它清掉
        self.assertTrue(store.begin("other"))
        store.finish("slow", "done")
        self.assertEqual(store.get("slow"), "done")


class TestTtlRenewedAtFinish(unittest.TestCase):
    """功能补全：收工即续期，长流程不必中途重跑。"""

    def test_full_ttl_granted_at_finish(self):
        clock = FakeClock()
        store = IdempotencyStore(ttl=30, clock=clock)
        store.begin("pay-66")
        clock.advance(20)
        clock.advance(20)                  # 共处理了 40 秒
        store.finish("pay-66", {"amount": 500})

        clock.advance(29)
        self.assertEqual(store.get("pay-66"), {"amount": 500})
        clock.advance(1)
        self.assertIsNone(store.get("pay-66"))


class TestTruncatedResult(unittest.TestCase):
    """功能补全：结果超上限落成截断标记，取回可识别。"""

    LIMIT = 64

    def setUp(self):
        self.store = IdempotencyStore(max_result_size=self.LIMIT)
        self.big = {"items": ["x" * 40, "y" * 40]}

    def test_small_result_stored_as_is(self):
        result = {"ok": True}
        self.assertIs(self.store.finish("small", result), result)
        self.assertIs(self.store.get("small"), result)

    def test_result_at_exact_limit_is_not_truncated(self):
        result = "a" * 5
        store = IdempotencyStore(
            max_result_size=len(json.dumps(result).encode("utf-8")))
        store.finish("exact", result)
        self.assertEqual(store.get("exact"), result)

    def test_oversize_result_becomes_marker(self):
        expected_size = len(json.dumps(self.big, ensure_ascii=False)
                            .encode("utf-8"))
        self.assertGreater(expected_size, self.LIMIT)

        stored = self.store.finish("pay-55", self.big)
        self.assertIsInstance(stored, TruncatedResult)
        self.assertEqual(stored.size, expected_size)
        self.assertEqual(stored.limit, self.LIMIT)

        replayed = self.store.get("pay-55")
        self.assertIsInstance(replayed, TruncatedResult)
        self.assertEqual(replayed, TruncatedResult(expected_size, self.LIMIT))

    def test_marker_round_trips_through_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "idem.json")
            before = IdempotencyStore(path=path, max_result_size=self.LIMIT)
            before.finish("pay-55", self.big)

            with open(path, "r", encoding="utf-8") as fh:
                on_disk = json.load(fh)
            self.assertNotIn("items", json.dumps(on_disk))

            after = IdempotencyStore(path=path, max_result_size=self.LIMIT)
            replayed = after.get("pay-55")
            self.assertIsInstance(replayed, TruncatedResult)
            self.assertEqual(replayed.limit, self.LIMIT)
            self.assertFalse(after.begin("pay-55"))

    def test_invalid_max_result_size_raises(self):
        for bad in (0, -1, 1.5, True, "64"):
            with self.assertRaises(ValueError):
                IdempotencyStore(max_result_size=bad)


if __name__ == "__main__":
    unittest.main()
