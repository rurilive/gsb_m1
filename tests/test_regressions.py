"""四类事故根因与新能力的防回归测试。"""

import json
import os
import tempfile
import threading
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
    """根因 1：lower() 归一化把只差大小写的两笔单并成一笔。"""

    def test_keys_differing_only_in_case_are_distinct(self):
        store = IdempotencyStore()
        self.assertTrue(store.begin("Order-7001"))
        store.finish("Order-7001", {"amount": 100})
        self.assertTrue(store.begin("order-7001"))
        store.finish("order-7001", {"amount": 80})
        self.assertEqual(store.get("Order-7001"), {"amount": 100})
        self.assertEqual(store.get("order-7001"), {"amount": 80})

    def test_surrounding_whitespace_is_still_trimmed(self):
        store = IdempotencyStore()
        store.finish(" pay-1 ", "receipt")
        self.assertEqual(store.get("pay-1"), "receipt")
        self.assertFalse(store.begin("\tpay-1\n"))

    def test_case_variants_survive_restart_independently(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "idem.json")
            first = IdempotencyStore(path=path, clock=FakeClock())
            first.finish("Aa", 1)
            first.finish("aA", 2)
            second = IdempotencyStore(path=path, clock=FakeClock())
            self.assertEqual(second.get("Aa"), 1)
            self.assertEqual(second.get("aA"), 2)


class TestPersistenceOnFinish(unittest.TestCase):
    """根因 2：finish 不落盘，重启后只剩空占位。"""

    def test_finished_result_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "idem.json")
            clock = FakeClock()
            before = IdempotencyStore(path=path, clock=clock)
            before.begin("pay-88")
            before.finish("pay-88", {"amount": 250, "state": "paid"})
            after = IdempotencyStore(path=path, clock=clock)
            self.assertEqual(after.get("pay-88"),
                             {"amount": 250, "state": "paid"})
            self.assertFalse(after.begin("pay-88"))

    def test_unfinished_placeholder_does_not_survive_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "idem.json")
            clock = FakeClock()
            before = IdempotencyStore(path=path, clock=clock)
            before.begin("crashed-midway")
            # 进程在这里崩溃：只留下了 begin 的占位。
            after = IdempotencyStore(path=path, clock=clock)
            self.assertTrue(after.begin("crashed-midway"))

    def test_finish_writes_valid_json_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "nested", "idem.json")
            store = IdempotencyStore(path=path, clock=FakeClock())
            store.begin("k")
            store.finish("k", {"ok": True})
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self.assertEqual(data["k"]["result"], {"ok": True})


class TestRollback(unittest.TestCase):
    """根因 3：处理中途失败，空占位把键永久卡死。"""

    def test_rollback_allows_reprocessing(self):
        store = IdempotencyStore()
        self.assertTrue(store.begin("pay-99"))
        self.assertTrue(store.rollback("pay-99"))
        self.assertTrue(store.begin("pay-99"))
        store.finish("pay-99", {"state": "paid"})
        self.assertEqual(store.get("pay-99"), {"state": "paid"})

    def test_rollback_does_not_touch_finished_record(self):
        store = IdempotencyStore()
        store.begin("pay-99")
        store.finish("pay-99", {"state": "paid"})
        self.assertFalse(store.rollback("pay-99"))
        self.assertEqual(store.get("pay-99"), {"state": "paid"})
        self.assertFalse(store.begin("pay-99"))

    def test_rollback_unknown_key_returns_false(self):
        store = IdempotencyStore()
        self.assertFalse(store.rollback("nope"))

    def test_rollback_is_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "idem.json")
            clock = FakeClock()
            store = IdempotencyStore(path=path, clock=clock)
            store.begin("pay-99")
            self.assertTrue(store.rollback("pay-99"))
            reopened = IdempotencyStore(path=path, clock=clock)
            self.assertTrue(reopened.begin("pay-99"))


class TestTtlFromFinish(unittest.TestCase):
    """根因 4：TTL 从开工时刻算，耗时单刚收工就被清掉。"""

    def test_long_running_request_survives_finish(self):
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
        clock.advance(2)
        self.assertIsNone(store.get("pay-77"))

    def test_pending_placeholder_still_expires_from_creation(self):
        clock = FakeClock()
        store = IdempotencyStore(ttl=60, clock=clock)
        store.begin("stuck-begin")
        clock.advance(61)
        self.assertTrue(store.begin("stuck-begin"))

    def test_expired_finished_record_can_be_processed_again(self):
        clock = FakeClock()
        store = IdempotencyStore(ttl=60, clock=clock)
        store.begin("pay-77")
        store.finish("pay-77", "first")
        clock.advance(61)
        self.assertTrue(store.begin("pay-77"))


class TestRenew(unittest.TestCase):
    """新能力：长流程中途/完成后续期。"""

    def test_renew_pending_key_mid_flight(self):
        clock = FakeClock()
        store = IdempotencyStore(ttl=60, clock=clock)
        store.begin("pay-66")
        clock.advance(50)
        self.assertTrue(store.renew("pay-66", ttl=120))
        clock.advance(100)            # 距开工 150 秒，越过原始 60 秒窗口
        # 别的请求触发清理：没有续期的话这里占位早被清掉了。
        self.assertFalse(store.begin("pay-66"))
        clock.advance(40)             # 仍在续期窗口（+120 秒）内
        store.finish("pay-66", {"amount": 500})
        self.assertEqual(store.get("pay-66"), {"amount": 500})

    def test_renew_finished_key_extends_from_finished_at(self):
        clock = FakeClock()
        store = IdempotencyStore(ttl=60, clock=clock)
        store.begin("pay-66")
        store.finish("pay-66", "receipt")
        clock.advance(55)
        self.assertTrue(store.renew("pay-66", ttl=120))
        clock.advance(60)            # 距完成 115 秒，越过默认 60 秒窗口
        self.assertEqual(store.get("pay-66"), "receipt")
        clock.advance(6)             # 距完成 121 秒，越过续期窗口
        self.assertIsNone(store.get("pay-66"))

    def test_renew_uses_default_ttl_without_argument(self):
        clock = FakeClock()
        store = IdempotencyStore(ttl=60, clock=clock)
        store.begin("pay-66")
        store.finish("pay-66", "receipt")
        self.assertTrue(store.renew("pay-66"))
        clock.advance(59)
        self.assertEqual(store.get("pay-66"), "receipt")

    def test_renew_unknown_key_returns_false(self):
        store = IdempotencyStore(ttl=60, clock=FakeClock())
        self.assertFalse(store.renew("nope"))

    def test_renew_invalid_ttl_raises(self):
        store = IdempotencyStore(ttl=60, clock=FakeClock())
        store.finish("k", 1)
        with self.assertRaises(ValueError):
            store.renew("k", ttl=0)

    def test_renew_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "idem.json")
            clock = FakeClock()
            before = IdempotencyStore(path=path, ttl=60, clock=clock)
            before.finish("pay-66", "receipt")
            clock.advance(50)
            before.renew("pay-66", ttl=300)
            after = IdempotencyStore(path=path, ttl=60, clock=clock)
            clock.advance(200)
            self.assertEqual(after.get("pay-66"), "receipt")


class TestTruncation(unittest.TestCase):
    """新能力：超大结果落成截断标记。"""

    def test_small_result_is_stored_as_is(self):
        store = IdempotencyStore(max_result_size=1024)
        store.finish("small", {"state": "paid"})
        self.assertEqual(store.get("small"), {"state": "paid"})

    def test_oversized_result_becomes_marker(self):
        store = IdempotencyStore(max_result_size=32)
        big = {"state": "paid", "receipt": "X" * 200}
        returned = store.finish("big", big)
        marker = store.get("big")
        self.assertIs(returned, marker)
        self.assertIsInstance(marker, TruncatedResult)
        self.assertTrue(marker.truncated)
        self.assertGreater(marker.original_size, 32)
        self.assertEqual(marker.size_limit, 32)
        self.assertEqual(marker, TruncatedResult(marker.original_size, 32))
        # 被截断的键仍算已处理，重复提交走回放而不是重新扣款。
        self.assertFalse(store.begin("big"))

    def test_result_exactly_at_limit_is_not_truncated(self):
        result = {"a": 1}
        size = len(json.dumps(result).encode("utf-8"))
        store = IdempotencyStore(max_result_size=size)
        store.finish("k", result)
        self.assertEqual(store.get("k"), result)

    def test_no_limit_means_never_truncate(self):
        store = IdempotencyStore()
        big = {"receipt": "Z" * 10000}
        store.finish("big", big)
        self.assertEqual(store.get("big"), big)

    def test_invalid_max_result_size_raises(self):
        with self.assertRaises(ValueError):
            IdempotencyStore(max_result_size=0)

    def test_truncated_marker_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "idem.json")
            clock = FakeClock()
            before = IdempotencyStore(
                path=path, clock=clock, max_result_size=32)
            before.finish("big", {"receipt": "Y" * 200})
            original = before.get("big")
            after = IdempotencyStore(
                path=path, clock=clock, max_result_size=32)
            marker = after.get("big")
            self.assertIsInstance(marker, TruncatedResult)
            self.assertEqual(marker, original)


class TestConcurrentBegin(unittest.TestCase):
    """并发送同一个键，只允许一单开工，占位语义不能被改坏。"""

    def test_only_one_beginner_wins(self):
        store = IdempotencyStore()
        winners = []
        barrier = threading.Barrier(8)

        def worker():
            barrier.wait()
            if store.begin("hot-key"):
                winners.append(threading.get_ident())

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(len(winners), 1)


if __name__ == "__main__":
    unittest.main()
