"""本轮新增行为的锁定测试。

覆盖：
- 负缓存：失败域名短时间内不再回源，有效期和正缓存分开配；
- single-flight：并发只放一个上游请求，失败广播给所有等待者；
- 半程预刷新：TTL 过半先给旧值、后台刷，刷失败顶到硬过期；
- TTL 抖动：幅度可配、随机源可注入、固定种子可复现；
- 边界：到点那一刻、对时回拨、零 TTL；
- 一万域名预热后六线程并发查询的性能门槛。

时钟一律注入 ManualClock（除真实验证并发窗口的用例外），
断言不依赖真实时间流逝；后台预刷新用例用 wait_for 等线程收尾。
"""

import random
import threading
import time
import unittest

from resolvcache.cache import (
    DEFAULT_JITTER,
    DEFAULT_NEGATIVE_TTL,
    REFRESH_FRACTION,
    ResolverCache,
)
from resolvcache.clock import ManualClock
from resolvcache.upstream import Answer, FakeUpstream, UpstreamError

START = 900.0
NAME = "a.svc.internal"


def wait_for(predicate, timeout=2.0, interval=0.002):
    """轮询等后台线程收尾，等到返回 True，超时返回最后一次结果。"""
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def get_entry(cache, name):
    with cache._lock:
        return cache._entries.get(name)


def make_cache(upstream=None, clock=None, default_ttl=30.0,
               negative_ttl=5.0, jitter=0.0, rng=None):
    """默认关掉抖动，绝大多数用例要的是确定性的到期边界。"""
    if upstream is None:
        upstream = FakeUpstream({NAME: ("10.0.0.1", 20.0)})
    if clock is None:
        clock = ManualClock(START)
    cache = ResolverCache(upstream, clock=clock, default_ttl=default_ttl,
                          negative_ttl=negative_ttl, jitter=jitter, rng=rng)
    return cache, upstream, clock


class BlockingUpstream(FakeUpstream):
    """resolve 会卡在放行事件上的上游，用来精确控制在飞航班的窗口。"""

    def __init__(self, zone, failing_names=()):
        super().__init__(zone)
        self._gate = threading.Event()  # 默认关着：resolve 一律先挡住
        self._failing_blocked = set(failing_names)

    def resolve(self, name):
        with self._lock:
            self._calls += 1
            self._calls_by_name[name] = self._calls_by_name.get(name, 0) + 1
            self._in_flight += 1
            if self._in_flight > self._peak_in_flight:
                self._peak_in_flight = self._in_flight
            failing = name in self._failing or name in self._failing_blocked
            record = self._zone.get(name)
        self._gate.wait(5.0)
        try:
            if failing or record is None:
                raise UpstreamError("upstream resolve failed: %s" % name)
            address, ttl = record
            return Answer(name, address, ttl)
        finally:
            with self._lock:
                self._in_flight -= 1

    def release(self):
        self._gate.set()

    def set_record(self, name, address, ttl):
        super().set_record(name, address, ttl)
        self._failing_blocked.discard(name)


class TestNegativeCaching(unittest.TestCase):
    def test_failed_name_is_remembered_and_not_requeried(self):
        cache, upstream, _ = make_cache(upstream=FakeUpstream({}))
        for _ in range(3):
            with self.assertRaises(UpstreamError):
                cache.lookup("dead.svc.internal")
        self.assertEqual(upstream.calls_for("dead.svc.internal"), 1)
        stats = cache.stats()
        self.assertEqual(stats["upstream_calls"], 1)
        self.assertEqual(stats["errors"], 3)
        # 每次 lookup 恰好计入一次命中或未命中。
        self.assertEqual(stats["hits"] + stats["misses"], 3)
        self.assertEqual(stats["entries"], 1)

    def test_negative_cache_survives_until_its_own_ttl(self):
        cache, upstream, clock = make_cache(upstream=FakeUpstream({}))
        with self.assertRaises(UpstreamError):
            cache.lookup("dead.svc.internal")
        clock.advance(4.99)
        with self.assertRaises(UpstreamError):
            cache.lookup("dead.svc.internal")
        self.assertEqual(upstream.calls_for("dead.svc.internal"), 1)

    def test_negative_cache_expires_at_exactly_its_ttl(self):
        cache, upstream, clock = make_cache(upstream=FakeUpstream({}))
        with self.assertRaises(UpstreamError):
            cache.lookup("dead.svc.internal")
        # 到点那一刻（now == expires_at）就算过期，重新回源。
        clock.advance(5.0)
        with self.assertRaises(UpstreamError):
            cache.lookup("dead.svc.internal")
        self.assertEqual(upstream.calls_for("dead.svc.internal"), 2)

    def test_recovery_after_negative_cache_expiry(self):
        upstream = FakeUpstream({})
        cache, _, clock = make_cache(upstream=upstream)
        with self.assertRaises(UpstreamError):
            cache.lookup(NAME)
        clock.advance(5.0)
        upstream.set_record(NAME, "10.0.0.7", 10.0)
        self.assertEqual(cache.lookup(NAME), "10.0.0.7")
        self.assertEqual(upstream.calls_for(NAME), 2)

    def test_negative_ttl_is_configured_separately_from_positive_ttl(self):
        cache, upstream, clock = make_cache(
            upstream=FakeUpstream({}), negative_ttl=10.0)
        with self.assertRaises(UpstreamError):
            cache.lookup("dead.svc.internal")
        clock.advance(9.99)
        with self.assertRaises(UpstreamError):
            cache.lookup("dead.svc.internal")
        self.assertEqual(upstream.calls_for("dead.svc.internal"), 1)
        clock.advance(0.01)
        with self.assertRaises(UpstreamError):
            cache.lookup("dead.svc.internal")
        self.assertEqual(upstream.calls_for("dead.svc.internal"), 2)

    def test_zero_negative_ttl_means_errors_are_never_remembered(self):
        cache, upstream, _ = make_cache(
            upstream=FakeUpstream({}), negative_ttl=0.0)
        for _ in range(2):
            with self.assertRaises(UpstreamError):
                cache.lookup("dead.svc.internal")
        self.assertEqual(upstream.calls_for("dead.svc.internal"), 2)
        self.assertEqual(cache.stats()["entries"], 0)


class TestSingleFlight(unittest.TestCase):
    def run_concurrent(self, cache, name, threads_count=10):
        results = []
        errors = []
        barrier = threading.Barrier(threads_count)
        result_lock = threading.Lock()

        def worker():
            barrier.wait()
            try:
                value = cache.lookup(name)
            except Exception as exc:  # noqa: BLE001
                with result_lock:
                    errors.append(exc)
            else:
                with result_lock:
                    results.append(value)

        threads = [threading.Thread(target=worker)
                   for _ in range(threads_count)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        return results, errors

    def test_only_one_upstream_call_for_concurrent_miss(self):
        upstream = FakeUpstream({NAME: ("10.0.0.1", 60.0)}, delay=0.05)
        cache = ResolverCache(upstream)
        results, errors = self.run_concurrent(cache, NAME)
        self.assertEqual(errors, [])
        self.assertEqual(results, ["10.0.0.1"] * 10)
        self.assertEqual(upstream.stats()["calls"], 1)
        self.assertEqual(upstream.stats()["peak_in_flight"], 1)
        stats = cache.stats()
        self.assertEqual(stats["upstream_calls"], 1)
        self.assertEqual(stats["hits"] + stats["misses"], 10)

    def test_failure_is_broadcast_to_every_waiter(self):
        upstream = FakeUpstream({}, delay=0.05)
        cache = ResolverCache(upstream, negative_ttl=5.0)
        name = "dead.svc.internal"
        results, errors = self.run_concurrent(cache, name)
        self.assertEqual(results, [])
        self.assertEqual(len(errors), 10)
        self.assertTrue(all(isinstance(exc, UpstreamError) for exc in errors))
        self.assertEqual(upstream.stats()["calls"], 1)
        self.assertEqual(upstream.stats()["peak_in_flight"], 1)
        self.assertEqual(cache.stats()["errors"], 10)
        # 广播完立刻重试，吃负缓存，不再打上游。
        with self.assertRaises(UpstreamError):
            cache.lookup(name)
        self.assertEqual(upstream.stats()["calls"], 1)

    def test_zero_ttl_concurrent_miss_is_still_coalesced(self):
        upstream = FakeUpstream({NAME: ("10.0.0.1", 0.0)}, delay=0.05)
        cache = ResolverCache(upstream)
        results, errors = self.run_concurrent(cache, NAME, threads_count=8)
        self.assertEqual(errors, [])
        self.assertEqual(results, ["10.0.0.1"] * 8)
        self.assertEqual(upstream.stats()["calls"], 1)
        self.assertEqual(upstream.stats()["peak_in_flight"], 1)
        # 零 TTL 不落缓存，并发这批散场后下一个请求照常回源。
        self.assertEqual(cache.lookup(NAME), "10.0.0.1")
        self.assertEqual(upstream.stats()["calls"], 2)


class TestBackgroundRefresh(unittest.TestCase):
    def test_half_ttl_lookup_serves_stale_and_refreshes_background(self):
        cache, upstream, clock = make_cache()
        self.assertEqual(cache.lookup(NAME), "10.0.0.1")
        upstream.set_record(NAME, "10.0.0.2", 20.0)
        clock.advance(10.0)  # 正好到半程，进入软过期。
        self.assertEqual(cache.lookup(NAME), "10.0.0.1")  # 旧值先顶着
        self.assertEqual(upstream.stats()["calls"], 2)
        self.assertTrue(wait_for(
            lambda: cache.stats()["refreshing"] == 0))
        self.assertEqual(cache.lookup(NAME), "10.0.0.2")
        self.assertEqual(upstream.stats()["calls"], 2)  # 没再回源

    def test_only_one_background_refresh_per_soft_window(self):
        upstream = FakeUpstream({NAME: ("10.0.0.1", 20.0)}, delay=0.05)
        cache, _, clock = make_cache(upstream=upstream)
        cache.lookup(NAME)
        upstream.set_record(NAME, "10.0.0.2", 20.0)
        clock.advance(10.0)
        for _ in range(6):
            self.assertEqual(cache.lookup(NAME), "10.0.0.1")
        self.assertEqual(upstream.stats()["calls"], 2)
        self.assertEqual(upstream.stats()["peak_in_flight"], 1)
        self.assertTrue(wait_for(
            lambda: cache.stats()["refreshing"] == 0))
        self.assertEqual(cache.lookup(NAME), "10.0.0.2")
        self.assertEqual(upstream.stats()["calls"], 2)

    def test_failed_refresh_keeps_serving_stale_until_hard_expiry(self):
        cache, upstream, clock = make_cache()
        cache.lookup(NAME)
        upstream.set_failing(NAME)
        clock.advance(10.0)
        # 半程后的查询拿到旧值，后台刷新失败。
        self.assertEqual(cache.lookup(NAME), "10.0.0.1")
        self.assertTrue(wait_for(
            lambda: cache.stats()["refreshing"] == 0))
        # 旧值窗口内再查：不补刷，继续顶旧值。
        clock.advance(5.0)
        self.assertEqual(cache.lookup(NAME), "10.0.0.1")
        self.assertEqual(upstream.stats()["calls"], 2)
        # 到硬过期点：同步回源，失败抛错。
        clock.advance(5.0)
        with self.assertRaises(UpstreamError):
            cache.lookup(NAME)
        self.assertEqual(upstream.stats()["calls"], 3)
        # 硬过期失败后由负缓存接手，不再回源。
        with self.assertRaises(UpstreamError):
            cache.lookup(NAME)
        self.assertEqual(upstream.stats()["calls"], 3)

    def test_hard_expiry_during_background_refresh_joins_the_flight(self):
        upstream = BlockingUpstream({NAME: ("10.0.0.1", 20.0)})
        cache, _, clock = make_cache(upstream=upstream)
        upstream.release()
        cache.lookup(NAME)
        upstream.set_record(NAME, "10.0.0.9", 20.0)
        clock.advance(10.0)
        self.assertEqual(cache.lookup(NAME), "10.0.0.1")  # 放出后台刷新
        self.assertTrue(wait_for(
            lambda: upstream.stats()["calls"] == 2))
        # 后台航班还在飞，时钟直接越过硬过期点：后来者等同一份结果。
        clock.advance(15.0)
        def join_after_release():
            upstream.release()

        releaser = threading.Timer(0.02, join_after_release)
        releaser.start()
        self.assertEqual(cache.lookup(NAME), "10.0.0.9")
        releaser.join()
        self.assertEqual(upstream.stats()["calls"], 2)
        self.assertEqual(upstream.stats()["peak_in_flight"], 1)

    def test_hard_expiry_waiter_gets_failure_and_negative_cache_takes_over(self):
        upstream = BlockingUpstream({NAME: ("10.0.0.1", 20.0)})
        cache, _, clock = make_cache(upstream=upstream)
        upstream.release()
        cache.lookup(NAME)
        upstream._failing_blocked.add(NAME)
        clock.advance(10.0)
        self.assertEqual(cache.lookup(NAME), "10.0.0.1")  # 旧值+失败航班
        self.assertTrue(wait_for(
            lambda: upstream.stats()["calls"] == 2))
        clock.advance(15.0)  # 已过硬过期点
        releaser = threading.Timer(0.02, upstream.release)
        releaser.start()
        with self.assertRaises(UpstreamError):
            cache.lookup(NAME)  # 等后台航班的失败广播
        releaser.join()
        self.assertEqual(upstream.stats()["calls"], 2)
        self.assertTrue(wait_for(
            lambda: cache.stats()["refreshing"] == 0))
        with self.assertRaises(UpstreamError):
            cache.lookup(NAME)  # 负缓存接手
        self.assertEqual(upstream.stats()["calls"], 2)


class TestBoundaries(unittest.TestCase):
    def test_positive_entry_is_fresh_before_soft_point(self):
        cache, upstream, clock = make_cache()
        cache.lookup(NAME)
        clock.set(START + 10.0 - 1e-9)
        self.assertEqual(cache.lookup(NAME), "10.0.0.1")
        self.assertEqual(cache.stats()["refreshing"], 0)
        self.assertEqual(upstream.stats()["calls"], 1)

    def test_soft_window_opens_exactly_at_half_ttl(self):
        cache, upstream, clock = make_cache()
        cache.lookup(NAME)
        clock.advance(10.0)
        self.assertEqual(cache.lookup(NAME), "10.0.0.1")  # 旧值
        self.assertEqual(upstream.stats()["calls"], 2)
        self.assertTrue(wait_for(
            lambda: cache.stats()["refreshing"] == 0))

    def test_positive_entry_hard_expires_exactly_at_expires_at(self):
        cache, upstream, clock = make_cache()
        cache.lookup(NAME)
        upstream.set_record(NAME, "10.0.0.8", 20.0)
        clock.advance(20.0)  # now == expires_at：到点即硬过期
        self.assertEqual(cache.lookup(NAME), "10.0.0.8")
        self.assertEqual(upstream.stats()["calls"], 2)
        self.assertEqual(cache.stats()["refreshing"], 0)

    def test_negative_entry_valid_an_instant_before_expiry(self):
        upstream = FakeUpstream({})
        cache, _, clock = make_cache(upstream=upstream)
        with self.assertRaises(UpstreamError):
            cache.lookup("dead.svc.internal")
        clock.set(START + 5.0 - 1e-9)
        with self.assertRaises(UpstreamError):
            cache.lookup("dead.svc.internal")
        self.assertEqual(upstream.calls_for("dead.svc.internal"), 1)
        clock.set(START + 5.0)
        with self.assertRaises(UpstreamError):
            cache.lookup("dead.svc.internal")
        self.assertEqual(upstream.calls_for("dead.svc.internal"), 2)

    def test_clock_rollback_makes_entry_fresh_again(self):
        cache, upstream, clock = make_cache()
        cache.lookup(NAME)
        clock.advance(30.0)  # 硬过期
        clock.set(START + 1.0)  # 对时回拨到半程之前
        self.assertEqual(cache.lookup(NAME), "10.0.0.1")
        self.assertEqual(upstream.stats()["calls"], 1)

    def test_clock_rollback_then_forward_reuses_same_deadline(self):
        # 回拨不补 TTL、不改到期时刻；再拨回硬过期点照样重查。
        cache, upstream, clock = make_cache()
        cache.lookup(NAME)
        upstream.set_record(NAME, "10.0.0.8", 20.0)
        clock.advance(25.0)
        clock.set(START + 1.0)
        self.assertEqual(cache.lookup(NAME), "10.0.0.1")
        clock.set(START + 20.0)
        self.assertEqual(cache.lookup(NAME), "10.0.0.8")
        self.assertEqual(upstream.stats()["calls"], 2)

    def test_zero_ttl_answer_is_not_cached(self):
        upstream = FakeUpstream({NAME: ("10.0.0.1", 0.0)})
        cache, _, _ = make_cache(upstream=upstream)
        cache.lookup(NAME)
        self.assertIsNone(get_entry(cache, NAME))
        cache.lookup(NAME)
        self.assertEqual(upstream.stats()["calls"], 2)

    def test_zero_default_ttl_means_no_cache(self):
        upstream = FakeUpstream({NAME: ("10.0.0.1", None)})
        cache, _, _ = make_cache(upstream=upstream, default_ttl=0.0)
        cache.lookup(NAME)
        self.assertIsNone(get_entry(cache, NAME))
        cache.lookup(NAME)
        self.assertEqual(upstream.stats()["calls"], 2)


class TestJitter(unittest.TestCase):
    def test_jitter_zero_uses_exact_ttl_boundaries(self):
        cache, _, _ = make_cache(jitter=0.0)
        cache.lookup(NAME)
        entry = get_entry(cache, NAME)
        self.assertAlmostEqual(entry.expires_at, START + 20.0)
        self.assertAlmostEqual(
            entry.soft_at, START + 20.0 * REFRESH_FRACTION)

    def test_jitter_spread_covers_both_sides_but_stays_in_range(self):
        ttl = 20.0
        expiries = []
        softs = []
        for seed in range(400):
            cache, _, _ = make_cache(jitter=0.5, rng=random.Random(seed))
            cache.lookup(NAME)
            entry = get_entry(cache, NAME)
            expiries.append(entry.expires_at)
            softs.append(entry.soft_at)
        self.assertTrue(min(expiries) < START + ttl * 0.6)
        self.assertTrue(max(expiries) > START + ttl * 1.4)
        self.assertGreaterEqual(min(expiries), START + ttl * 0.5 - 1e-9)
        self.assertLessEqual(max(expiries), START + ttl * 1.5 + 1e-9)
        # 软过期点始终是抖动后有效期的正中间。
        for entry_expiry, entry_soft in zip(expiries, softs):
            self.assertAlmostEqual(
                entry_soft, START + (entry_expiry - START)
                * REFRESH_FRACTION)

    def test_injected_rng_makes_expiry_deterministic(self):
        def expiry_with_seed(seed):
            cache, _, _ = make_cache(jitter=0.2, rng=random.Random(seed))
            cache.lookup(NAME)
            return get_entry(cache, NAME).expires_at

        first = expiry_with_seed(123)
        self.assertEqual(first, expiry_with_seed(123))
        self.assertNotEqual(first, expiry_with_seed(124))

    def test_jitter_applies_to_negative_entries_too(self):
        upstream = FakeUpstream({})
        cache, _, clock = make_cache(
            upstream=upstream, negative_ttl=10.0, jitter=0.5,
            rng=random.Random(7))
        with self.assertRaises(UpstreamError):
            cache.lookup("dead.svc.internal")
        entry = get_entry(cache, "dead.svc.internal")
        self.assertGreaterEqual(entry.expires_at, START + 5.0 - 1e-9)
        self.assertLessEqual(entry.expires_at, START + 15.0 + 1e-9)
        self.assertNotAlmostEqual(entry.expires_at, START + 10.0)

    def test_defaults_are_published(self):
        self.assertEqual(DEFAULT_NEGATIVE_TTL, 5.0)
        self.assertEqual(DEFAULT_JITTER, 0.1)
        cache = ResolverCache(FakeUpstream({}))
        self.assertEqual(cache._negative_ttl, DEFAULT_NEGATIVE_TTL)
        self.assertEqual(cache._jitter, DEFAULT_JITTER)

    def test_invalid_constructor_arguments_raise(self):
        with self.assertRaises(ValueError):
            ResolverCache(FakeUpstream({}), default_ttl=-1.0)
        with self.assertRaises(ValueError):
            ResolverCache(FakeUpstream({}), negative_ttl=-1.0)
        with self.assertRaises(ValueError):
            ResolverCache(FakeUpstream({}), jitter=1.1)
        with self.assertRaises(ValueError):
            ResolverCache(FakeUpstream({}), jitter=-0.1)


class TestPerformance(unittest.TestCase):
    def test_10k_warmup_six_threads_120k_lookups_under_four_seconds(self):
        domain_count = 10000
        per_thread = 20000
        zone = {
            "host%05d.svc.internal" % i:
            ("10.%d.%d.%d" % (i // 65025, (i // 256) % 254 + 1,
                              i % 254 + 1), 600.0)
            for i in range(domain_count)
        }
        upstream = FakeUpstream(zone)
        cache = ResolverCache(upstream)

        for i in range(domain_count):
            self.assertEqual(
                cache.lookup("host%05d.svc.internal" % i),
                zone["host%05d.svc.internal" % i][0])
        self.assertEqual(upstream.stats()["calls"], domain_count)

        errors = []
        errors_lock = threading.Lock()

        def worker(seed):
            rng = random.Random(seed)
            for _ in range(per_thread):
                index = rng.randrange(domain_count)
                name = "host%05d.svc.internal" % index
                if cache.lookup(name) != zone[name][0]:
                    with errors_lock:
                        errors.append(name)

        threads = [threading.Thread(target=worker, args=(seed,))
                   for seed in range(6)]
        started = time.perf_counter()
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        elapsed = time.perf_counter() - started

        self.assertEqual(errors, [])
        self.assertLess(elapsed, 4.0, "120k 并发查询耗时 %.3fs 超过 4s" % elapsed)
        # 长 TTL 预热后，压测期间不该有任何回源或后台预刷新。
        self.assertEqual(upstream.stats()["calls"], domain_count)


if __name__ == "__main__":
    unittest.main()
