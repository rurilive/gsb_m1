"""ResolverCache 现有行为的锁定测试。

时钟与上游都是注入的，断言全部基于注入时钟的读数，
不依赖真实时间流逝。
"""

import threading
import unittest

from resolvcache.cache import ResolverCache
from resolvcache.clock import ManualClock
from resolvcache.upstream import FakeUpstream, UpstreamError

START = 500.0


class TestLookupBasics(unittest.TestCase):
    def setUp(self):
        self.upstream = FakeUpstream({
            "a.svc.internal": ("10.0.0.1", 20.0),
            "b.svc.internal": ("10.0.0.2", None),
        })
        self.clock = ManualClock(START)
        self.cache = ResolverCache(self.upstream, clock=self.clock,
                                   default_ttl=30.0)

    def test_miss_goes_upstream_and_returns_address(self):
        self.assertEqual(self.cache.lookup("a.svc.internal"), "10.0.0.1")
        self.assertEqual(self.upstream.stats()["calls"], 1)
        stats = self.cache.stats()
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["hits"], 0)
        self.assertEqual(stats["upstream_calls"], 1)

    def test_second_lookup_is_a_hit(self):
        self.cache.lookup("a.svc.internal")
        self.assertEqual(self.cache.lookup("a.svc.internal"), "10.0.0.1")
        self.assertEqual(self.upstream.stats()["calls"], 1)
        stats = self.cache.stats()
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)

    def test_entry_is_refetched_once_it_is_well_past_ttl(self):
        self.cache.lookup("a.svc.internal")
        # 上游这条记录换了地址，有效期 20 秒，推进到远超 20 秒之后再查
        self.upstream.set_record("a.svc.internal", "10.0.0.9", 20.0)
        self.clock.advance(90.0)
        self.assertEqual(self.cache.lookup("a.svc.internal"), "10.0.0.9")
        self.assertEqual(self.upstream.stats()["calls"], 2)

    def test_default_ttl_applies_when_upstream_omits_ttl(self):
        self.assertEqual(self.cache.lookup("b.svc.internal"), "10.0.0.2")
        self.clock.advance(5.0)
        self.assertEqual(self.cache.lookup("b.svc.internal"), "10.0.0.2")
        self.assertEqual(self.upstream.stats()["calls"], 1)
        self.clock.advance(300.0)
        self.assertEqual(self.cache.lookup("b.svc.internal"), "10.0.0.2")
        self.assertEqual(self.upstream.stats()["calls"], 2)

    def test_unknown_name_raises_upstream_error(self):
        with self.assertRaises(UpstreamError):
            self.cache.lookup("nope.svc.internal")

    def test_stats_exposes_the_same_counters(self):
        self.cache.lookup("a.svc.internal")
        stats = self.cache.stats()
        for key in ("hits", "misses", "upstream_calls", "errors", "entries"):
            self.assertIn(key, stats)
        self.assertEqual(stats["entries"], 1)


class TestUpstreamFailures(unittest.TestCase):
    def setUp(self):
        self.upstream = FakeUpstream({"a.svc.internal": ("10.0.0.1", 20.0)})
        self.clock = ManualClock(START)
        self.cache = ResolverCache(self.upstream, clock=self.clock,
                                   default_ttl=30.0)

    def test_error_reaches_the_caller_and_is_counted(self):
        self.upstream.set_failing("a.svc.internal")
        with self.assertRaises(UpstreamError):
            self.cache.lookup("a.svc.internal")
        self.assertEqual(self.cache.stats()["errors"], 1)

    def test_failed_name_recovers_once_the_upstream_is_back(self):
        self.upstream.set_failing("a.svc.internal")
        with self.assertRaises(UpstreamError):
            self.cache.lookup("a.svc.internal")
        self.upstream.set_record("a.svc.internal", "10.0.0.7", 20.0)
        self.clock.advance(3600.0)
        self.assertEqual(self.cache.lookup("a.svc.internal"), "10.0.0.7")
        self.assertEqual(self.upstream.stats()["calls"], 2)


class TestConcurrentLookups(unittest.TestCase):
    def test_every_thread_gets_the_address_of_its_own_name(self):
        names = ["host%03d.svc.internal" % i for i in range(240)]
        zone = {name: ("10.1.%d.%d" % (i // 250, i % 250 + 1), 60.0)
                for i, name in enumerate(names)}
        upstream = FakeUpstream(zone, delay=0.001)
        clock = ManualClock(START)
        cache = ResolverCache(upstream, clock=clock)
        errors = []

        def worker(chunk):
            try:
                for name in chunk:
                    address = cache.lookup(name)
                    expected = zone[name][0]
                    if address != expected:
                        errors.append((name, address, expected))
                    if cache.lookup(name) != expected:
                        errors.append((name, "second lookup"))
            except Exception as exc:  # noqa: BLE001
                errors.append((exc.__class__.__name__, str(exc)))

        threads = [threading.Thread(target=worker, args=(names[i::6],))
                   for i in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertEqual(upstream.stats()["calls"], len(names))
        self.assertEqual(cache.stats()["entries"], len(names))


if __name__ == "__main__":
    unittest.main()
