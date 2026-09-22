"""本轮新行为的锁定测试：负缓存、单飞、后台预刷新、抖动与边界规则。

时钟、上游、随机源全部注入，断言不依赖真实时间流逝；
唯一的例外是后台预刷新线程，用带截止时间的轮询等它落地。
"""

import random
import threading
import time
import unittest

from resolvcache.cache import ResolverCache
from resolvcache.clock import ManualClock
from resolvcache.upstream import FakeUpstream, UpstreamError

START = 500.0


def wait_for(predicate, timeout=2.0):
    """轮询等后台线程落地，超时返回 False。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.001)
    return predicate()


def cache_lookup(cache):
    return cache.lookup("a.svc.internal")


class TestNegativeCache(unittest.TestCase):
    def setUp(self):
        self.upstream = FakeUpstream({"a.svc.internal": ("10.0.0.1", 20.0)})
        self.clock = ManualClock(START)
        self.cache = ResolverCache(self.upstream, clock=self.clock,
                                   negative_ttl=5.0)
        self.upstream.set_failing("a.svc.internal")

    def test_failure_is_cached_and_upstream_is_not_hit_again(self):
        for _ in range(5):
            with self.assertRaises(UpstreamError):
                self.cache.lookup("a.svc.internal")
        self.assertEqual(self.upstream.stats()["calls"], 1)
        self.assertEqual(self.cache.stats()["errors"], 1)

    def test_negative_entry_expires_and_retries_upstream(self):
        with self.assertRaises(UpstreamError):
            self.cache.lookup("a.svc.internal")
        self.clock.advance(6.0)
        with self.assertRaises(UpstreamError):
            self.cache.lookup("a.svc.internal")
        self.assertEqual(self.upstream.stats()["calls"], 2)

    def test_negative_ttl_is_configured_separately_from_success(self):
        cache = ResolverCache(self.upstream, clock=self.clock,
                              negative_ttl=2.0)
        with self.assertRaises(UpstreamError):
            cache.lookup("a.svc.internal")
        self.clock.advance(3.0)
        with self.assertRaises(UpstreamError):
            cache.lookup("a.svc.internal")
        self.assertEqual(self.upstream.stats()["calls"], 2)

    def test_zero_negative_ttl_disables_negative_caching(self):
        cache = ResolverCache(self.upstream, clock=self.clock,
                              negative_ttl=0.0)
        for _ in range(3):
            with self.assertRaises(UpstreamError):
                cache.lookup("a.svc.internal")
        self.assertEqual(self.upstream.stats()["calls"], 3)

    def test_recovery_after_negative_entry_expires(self):
        with self.assertRaises(UpstreamError):
            self.cache.lookup("a.svc.internal")
        self.upstream.set_record("a.svc.internal", "10.0.0.7", 20.0)
        self.clock.advance(6.0)
        self.assertEqual(self.cache.lookup("a.svc.internal"), "10.0.0.7")
        self.assertEqual(self.upstream.stats()["calls"], 2)


class TestSingleflight(unittest.TestCase):
    def setUp(self):
        self.clock = ManualClock(START)

    def _run_threads(self, worker, count=8):
        threads = [threading.Thread(target=worker) for _ in range(count)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

    def test_concurrent_miss_shares_one_upstream_call(self):
        upstream = FakeUpstream({"hot.svc.internal": ("10.0.0.30", 60.0)},
                                delay=0.1)
        cache = ResolverCache(upstream, clock=self.clock)
        results = []
        lock = threading.Lock()

        def worker():
            address = cache.lookup("hot.svc.internal")
            with lock:
                results.append(address)

        self._run_threads(worker)
        self.assertEqual(results, ["10.0.0.30"] * 8)
        self.assertEqual(upstream.stats()["calls"], 1)
        stats = cache.stats()
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["upstream_calls"], 1)

    def test_upstream_error_is_broadcast_to_all_waiters(self):
        upstream = FakeUpstream({"hot.svc.internal": ("10.0.0.30", 60.0)},
                                delay=0.1)
        upstream.set_failing("hot.svc.internal")
        cache = ResolverCache(upstream, clock=self.clock)
        errors = []
        lock = threading.Lock()

        def worker():
            try:
                cache.lookup("hot.svc.internal")
            except UpstreamError:
                with lock:
                    errors.append("error")

        self._run_threads(worker)
        self.assertEqual(errors, ["error"] * 8)
        self.assertEqual(upstream.stats()["calls"], 1)
        self.assertEqual(cache.stats()["errors"], 1)


class TestBackgroundRefresh(unittest.TestCase):
    def setUp(self):
        self.upstream = FakeUpstream({"a.svc.internal": ("10.0.0.1", 20.0)})
        self.clock = ManualClock(START)
        self.cache = ResolverCache(self.upstream, clock=self.clock)

    def test_hit_past_half_ttl_triggers_background_refresh(self):
        self.assertEqual(self.cache.lookup("a.svc.internal"), "10.0.0.1")
        self.upstream.set_record("a.svc.internal", "10.0.0.9", 20.0)
        self.clock.advance(11.0)  # 有效期 20 秒，已过半
        # 命中先返回旧值，后台同时起刷新
        self.assertEqual(self.cache.lookup("a.svc.internal"), "10.0.0.1")
        self.assertTrue(
            wait_for(lambda: self.upstream.stats()["calls"] == 2))
        self.assertTrue(
            wait_for(lambda: cache_lookup(self.cache) == "10.0.0.9"))
        self.assertEqual(self.cache.lookup("a.svc.internal"), "10.0.0.9")
        stats = self.cache.stats()
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["upstream_calls"], 2)

    def test_refresh_is_singleflight_per_entry(self):
        self.cache.lookup("a.svc.internal")
        self.clock.advance(11.0)
        for _ in range(5):
            self.cache.lookup("a.svc.internal")
        self.assertTrue(
            wait_for(lambda: self.upstream.stats()["calls"] >= 2))
        time.sleep(0.05)
        self.assertEqual(self.upstream.stats()["calls"], 2)

    def test_failed_refresh_serves_stale_until_hard_expiry(self):
        self.assertEqual(self.cache.lookup("a.svc.internal"), "10.0.0.1")
        self.upstream.set_failing("a.svc.internal")
        self.clock.advance(11.0)  # 过半，触发的后台刷新会失败
        self.assertEqual(self.cache.lookup("a.svc.internal"), "10.0.0.1")
        self.assertTrue(wait_for(lambda: self.cache.stats()["errors"] == 1))
        calls = self.upstream.stats()["calls"]
        # 刷新失败不再重试，旧值顶到硬过期
        self.clock.advance(5.0)
        self.assertEqual(self.cache.lookup("a.svc.internal"), "10.0.0.1")
        self.assertEqual(self.upstream.stats()["calls"], calls)
        # 硬过期后按未命中重新回源，失败抛给调用方并记负缓存
        self.clock.advance(5.0)
        with self.assertRaises(UpstreamError):
            self.cache.lookup("a.svc.internal")
        self.assertEqual(self.upstream.stats()["calls"], calls + 1)

    def test_refresh_can_be_turned_off(self):
        cache = ResolverCache(self.upstream, clock=self.clock, refresh=False)
        cache.lookup("a.svc.internal")
        self.clock.advance(15.0)
        self.assertEqual(cache.lookup("a.svc.internal"), "10.0.0.1")
        time.sleep(0.05)
        self.assertEqual(self.upstream.stats()["calls"], 1)

    def test_negative_entries_are_not_refreshed(self):
        self.upstream.set_failing("a.svc.internal")
        with self.assertRaises(UpstreamError):
            self.cache.lookup("a.svc.internal")
        self.clock.advance(3.0)  # 负缓存 5 秒，已过半
        with self.assertRaises(UpstreamError):
            self.cache.lookup("a.svc.internal")
        time.sleep(0.05)
        self.assertEqual(self.upstream.stats()["calls"], 1)


class TestJitter(unittest.TestCase):
    def setUp(self):
        self.upstream = FakeUpstream({"a.svc.internal": ("10.0.0.1", 20.0)})
        self.clock = ManualClock(START)

    def test_positive_ttl_jitter_with_fixed_seed(self):
        rng = random.Random(7)
        cache = ResolverCache(self.upstream, clock=self.clock,
                              jitter=0.5, rng=rng, refresh=False)
        expected = 20.0 * (1.0 + random.Random(7).uniform(-0.5, 0.5))
        cache.lookup("a.svc.internal")
        self.clock.advance(expected - 0.5)
        self.assertEqual(cache.lookup("a.svc.internal"), "10.0.0.1")
        self.assertEqual(self.upstream.stats()["calls"], 1)
        self.clock.advance(1.0)
        self.assertEqual(cache.lookup("a.svc.internal"), "10.0.0.1")
        self.assertEqual(self.upstream.stats()["calls"], 2)

    def test_negative_ttl_jitter_with_fixed_seed(self):
        rng = random.Random(11)
        cache = ResolverCache(self.upstream, clock=self.clock,
                              negative_ttl=10.0, jitter=0.5, rng=rng)
        expected = 10.0 * (1.0 + random.Random(11).uniform(-0.5, 0.5))
        self.upstream.set_failing("a.svc.internal")
        with self.assertRaises(UpstreamError):
            cache.lookup("a.svc.internal")
        self.clock.advance(expected - 0.5)
        with self.assertRaises(UpstreamError):
            cache.lookup("a.svc.internal")
        self.assertEqual(self.upstream.stats()["calls"], 1)
        self.clock.advance(1.0)
        with self.assertRaises(UpstreamError):
            cache.lookup("a.svc.internal")
        self.assertEqual(self.upstream.stats()["calls"], 2)

    def test_same_seed_reproduces_the_same_expiry(self):
        def expiry_with(seed):
            upstream = FakeUpstream({"a.svc.internal": ("10.0.0.1", 20.0)})
            clock = ManualClock(START)
            cache = ResolverCache(upstream, clock=clock, jitter=0.5,
                                  rng=random.Random(seed), refresh=False)
            cache.lookup("a.svc.internal")
            low, high = 0.0, 20.0
            for _ in range(40):
                mid = (low + high) / 2.0
                clock.set(START + mid)
                before = upstream.stats()["calls"]
                cache.lookup("a.svc.internal")
                if upstream.stats()["calls"] == before:
                    low = mid
                else:
                    high = mid
            return low

        self.assertAlmostEqual(expiry_with(99), expiry_with(99), places=9)

    def test_invalid_jitter_is_rejected(self):
        with self.assertRaises(ValueError):
            ResolverCache(self.upstream, clock=self.clock, jitter=1.0)
        with self.assertRaises(ValueError):
            ResolverCache(self.upstream, clock=self.clock, jitter=-0.1)


class TestBoundaryRules(unittest.TestCase):
    def setUp(self):
        self.upstream = FakeUpstream({
            "a.svc.internal": ("10.0.0.1", 20.0),
            "zero.svc.internal": ("10.0.0.2", 0.0),
            "neg.svc.internal": ("10.0.0.3", -5.0),
        })
        self.clock = ManualClock(START)
        # 关掉预刷新，只锁读路径上的边界判断
        self.cache = ResolverCache(self.upstream, clock=self.clock,
                                   refresh=False)

    def test_entry_is_still_valid_at_the_exact_expiry_instant(self):
        self.cache.lookup("a.svc.internal")
        self.clock.advance(20.0)  # 正好到点，仍算命中
        self.assertEqual(self.cache.lookup("a.svc.internal"), "10.0.0.1")
        self.assertEqual(self.upstream.stats()["calls"], 1)
        self.clock.advance(0.001)  # 过了到点那一刻才算过期
        self.assertEqual(self.cache.lookup("a.svc.internal"), "10.0.0.1")
        self.assertEqual(self.upstream.stats()["calls"], 2)

    def test_clock_rollback_invalidates_all_entries(self):
        self.cache.lookup("a.svc.internal")
        self.assertEqual(self.upstream.stats()["calls"], 1)
        self.clock.set(START - 100.0)  # 对时回拨
        self.assertEqual(self.cache.lookup("a.svc.internal"), "10.0.0.1")
        self.assertEqual(self.upstream.stats()["calls"], 2)
        self.assertEqual(self.cache.stats()["entries"], 1)

    def test_zero_ttl_answer_is_never_cached(self):
        self.assertEqual(self.cache.lookup("zero.svc.internal"), "10.0.0.2")
        self.assertEqual(self.cache.lookup("zero.svc.internal"), "10.0.0.2")
        self.assertEqual(self.upstream.stats()["calls"], 2)
        self.assertEqual(self.cache.stats()["entries"], 0)

    def test_negative_ttl_answer_is_never_cached(self):
        self.assertEqual(self.cache.lookup("neg.svc.internal"), "10.0.0.3")
        self.assertEqual(self.cache.lookup("neg.svc.internal"), "10.0.0.3")
        self.assertEqual(self.upstream.stats()["calls"], 2)
        self.assertEqual(self.cache.stats()["entries"], 0)


class TestPrewarmedHotPath(unittest.TestCase):
    def test_10k_prewarmed_domains_6_threads_20k_lookups_each(self):
        names = ["node%05d.svc.internal" % i for i in range(10000)]
        zone = {name: ("10.2.%d.%d" % (i // 250, i % 250 + 1), 300.0)
                for i, name in enumerate(names)}
        upstream = FakeUpstream(zone)
        clock = ManualClock(START)
        cache = ResolverCache(upstream, clock=clock)
        for name in names:
            cache.lookup(name)
        self.assertEqual(upstream.stats()["calls"], len(names))

        errors = []
        started = threading.Barrier(6)

        def worker(seed):
            rng = random.Random(seed)
            started.wait()
            try:
                for _ in range(20000):
                    name = names[rng.randrange(len(names))]
                    if cache.lookup(name) != zone[name][0]:
                        errors.append(name)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,))
                   for i in range(6)]
        begin = time.monotonic()
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        elapsed = time.monotonic() - begin
        self.assertEqual(errors, [])
        self.assertEqual(upstream.stats()["calls"], len(names))
        self.assertLess(elapsed, 4.0, "热路径 %.2fs 超过 4s 预算" % elapsed)


if __name__ == "__main__":
    unittest.main()
