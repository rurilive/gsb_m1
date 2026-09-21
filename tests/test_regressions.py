"""四类线上事故的防回归测试，外加续期与结果截断两项增强。

每个测试类对应 README "Known Issues" 里的一条：
  1. 大小写不同的键不得并成同一笔
  2. finish 必须落盘，重启后结果可回放
  3. 处理中途失败要能 release 占位、重发重新开工
  4. ttl 从完成时刻起算，长流程可 renew 续期
  5. 超上限结果落成截断标记
"""

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
    """事故 1：只差大小写的两笔单必须各算各的。"""

    def test_case_variants_are_distinct_keys(self):
        store = IdempotencyStore()
        self.assertTrue(store.begin("Order-7001"))
        store.finish("Order-7001", {"amount": 100})
        self.assertTrue(store.begin("order-7001"))
        store.finish("order-7001", {"amount": 200})
        self.assertEqual(store.get("Order-7001"), {"amount": 100})
        self.assertEqual(store.get("order-7001"), {"amount": 200})

    def test_case_variants_distinct_after_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "idem.json")
            store = IdempotencyStore(path=path)
            store.finish("Order-1", "upper")
            store.finish("order-1", "lower")
            reloaded = IdempotencyStore(path=path)
            self.assertEqual(reloaded.get("Order-1"), "upper")
            self.assertEqual(reloaded.get("order-1"), "lower")

    def test_whitespace_is_still_trimmed(self):
        store = IdempotencyStore()
        store.finish(" pay-1 ", 9)
        self.assertEqual(store.get("pay-1"), 9)


class TestFinishIsPersisted(unittest.TestCase):
    """事故 2：重启后结果必须还在，重发回放而不是判死重复。"""

    def test_finished_result_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "idem.json")
            before = IdempotencyStore(path=path)
            before.begin("pay-88")
            before.finish("pay-88", {"amount": 250, "state": "paid"})
            after = IdempotencyStore(path=path)
            self.assertEqual(
                after.get("pay-88"), {"amount": 250, "state": "paid"}
            )
            self.assertFalse(after.begin("pay-88"))

    def test_every_finish_is_flushed_to_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "idem.json")
            store = IdempotencyStore(path=path)
            store.begin("pay-88")
            store.finish("pay-88", {"amount": 250})
            with open(path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            self.assertEqual(raw["pay-88"]["result"], {"amount": 250})
            self.assertIsNotNone(raw["pay-88"]["finished_at"])

    def test_partial_write_does_not_corrupt_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "idem.json")
            store = IdempotencyStore(path=path)
            store.finish("pay-1", "first")
            store.finish("pay-2", "second")
            files = os.listdir(tmp)
            self.assertEqual(files, [os.path.basename(path)])
            reloaded = IdempotencyStore(path=path)
            self.assertEqual(reloaded.get("pay-1"), "first")
            self.assertEqual(reloaded.get("pay-2"), "second")


class TestReleaseAfterFailure(unittest.TestCase):
    """事故 3：中途失败放开占位，重发可以重新开工。"""

    def test_released_key_can_begin_again(self):
        store = IdempotencyStore()
        self.assertTrue(store.begin("pay-99"))
        self.assertTrue(store.release("pay-99"))
        self.assertTrue(store.begin("pay-99"))

    def test_release_then_finish_replays_new_result(self):
        store = IdempotencyStore()
        store.begin("pay-99")
        store.release("pay-99")
        store.begin("pay-99")
        store.finish("pay-99", {"state": "paid"})
        self.assertEqual(store.get("pay-99"), {"state": "paid"})
        self.assertFalse(store.begin("pay-99"))

    def test_release_does_not_touch_finished_record(self):
        store = IdempotencyStore()
        store.finish("pay-99", {"state": "paid"})
        self.assertFalse(store.release("pay-99"))
        self.assertEqual(store.get("pay-99"), {"state": "paid"})
        self.assertFalse(store.begin("pay-99"))

    def test_release_unknown_key_returns_false(self):
        store = IdempotencyStore()
        self.assertFalse(store.release("nope"))

    def test_release_is_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "idem.json")
            store = IdempotencyStore(path=path)
            store.begin("pay-99")
            self.assertTrue(store.release("pay-99"))
            reloaded = IdempotencyStore(path=path)
            self.assertTrue(reloaded.begin("pay-99"))

    def test_orphan_placeholder_expires_by_created_at(self):
        clock = FakeClock()
        store = IdempotencyStore(ttl=60, clock=clock)
        store.begin("pay-99")           # 占了键但没人 finish / release
        clock.advance(60)
        self.assertTrue(store.begin("pay-99"))


class TestTtlFromFinishAndRenew(unittest.TestCase):
    """事故 4：ttl 锚完成时刻；renew 给长流程续期。"""

    def test_long_running_result_survives_full_ttl_after_finish(self):
        clock = FakeClock()
        store = IdempotencyStore(ttl=60, clock=clock)
        store.begin("pay-77")
        clock.advance(90)              # 开工到收工 90 秒，已超 ttl
        store.finish("pay-77", "receipt")
        self.assertEqual(store.get("pay-77"), "receipt")
        clock.advance(59)
        self.assertEqual(store.get("pay-77"), "receipt")
        clock.advance(1)
        self.assertIsNone(store.get("pay-77"))

    def test_renew_keeps_inflight_placeholder_alive(self):
        clock = FakeClock()
        store = IdempotencyStore(ttl=60, clock=clock)
        store.begin("pay-78")
        clock.advance(40)
        self.assertTrue(store.renew("pay-78"))
        clock.advance(40)
        self.assertFalse(store.begin("pay-78"))
        store.finish("pay-78", "receipt")
        self.assertEqual(store.get("pay-78"), "receipt")

    def test_renew_finished_key_restarts_ttl_window(self):
        clock = FakeClock()
        store = IdempotencyStore(ttl=60, clock=clock)
        store.begin("pay-78")
        store.finish("pay-78", "receipt")
        clock.advance(50)
        self.assertTrue(store.renew("pay-78"))
        clock.advance(50)
        self.assertEqual(store.get("pay-78"), "receipt")

    def test_renew_unknown_key_returns_false(self):
        store = IdempotencyStore()
        self.assertFalse(store.renew("nope"))

    def test_renew_is_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "idem.json")
            store = IdempotencyStore(path=path)
            store.begin("pay-78")
            self.assertTrue(store.renew("pay-78"))
            with open(path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            self.assertIn("pay-78", raw)


class TestOversizeResultTruncation(unittest.TestCase):
    """增强：超大结果落成截断标记，不撑爆缓存。"""

    def test_small_result_is_stored_as_is(self):
        store = IdempotencyStore(max_result_size=1024)
        result = {"state": "paid"}
        self.assertIs(store.finish("pay-1", result), result)
        self.assertEqual(store.get("pay-1"), result)

    def test_oversize_result_becomes_marker(self):
        store = IdempotencyStore(max_result_size=32)
        big = {"receipt": "x" * 200}
        stored = store.finish("pay-1", big)
        self.assertIsInstance(stored, TruncatedResult)
        self.assertTrue(stored.truncated)
        self.assertGreater(stored.original_size, 32)
        self.assertEqual(stored.max_size, 32)
        fetched = store.get("pay-1")
        self.assertIsInstance(fetched, TruncatedResult)
        self.assertTrue(fetched.truncated)
        self.assertEqual(fetched, stored)

    def test_truncated_marker_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "idem.json")
            store = IdempotencyStore(path=path, max_result_size=32)
            store.finish("pay-1", {"receipt": "x" * 200})
            reloaded = IdempotencyStore(path=path, max_result_size=32)
            fetched = reloaded.get("pay-1")
            self.assertIsInstance(fetched, TruncatedResult)
            self.assertTrue(fetched.truncated)
            self.assertEqual(fetched.max_size, 32)

    def test_truncated_key_still_counts_as_processed(self):
        store = IdempotencyStore(max_result_size=32)
        store.begin("pay-1")
        store.finish("pay-1", {"receipt": "x" * 200})
        self.assertFalse(store.begin("pay-1"))

    def test_invalid_max_result_size_raises(self):
        with self.assertRaises(ValueError):
            IdempotencyStore(max_result_size=0)


if __name__ == "__main__":
    unittest.main()
