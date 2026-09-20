"""四个缓存故障修复后的回归测试（与基线测试互相独立）。"""

import threading
import time
import unittest

from guardcache import GuardCache, NotFound


class FakeClock:
    """手动推进的时钟。"""

    def __init__(self, start=1000.0):
        self.now = float(start)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class GatedLoader:
    """进入 loader 后阻塞在门控上的加载器，用于构造并发未命中。"""

    def __init__(self, make_result):
        self.entered = threading.Event()
        self.release = threading.Event()
        self.calls = []
        self._make_result = make_result

    def __call__(self, key):
        self.calls.append(key)
        self.entered.set()
        if not self.release.wait(5.0):
            raise AssertionError("loader 未被放行")
        return self._make_result(key, len(self.calls))


def run_concurrent(cache, key, n, loader, timeout=5.0):
    """领头请求进入 loader 后再放行其余 n-1 个并发请求，最后一起放行。

    返回 (results, errors)，按线程顺序记录各自的返回值和异常。
    """
    results = [None] * n
    errors = [None] * n

    def worker(i):
        try:
            results[i] = cache.get(key)
        except BaseException as exc:
            errors[i] = exc

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    threads[0].start()
    if not loader.entered.wait(timeout):
        raise AssertionError("loader 未在预期时间内被调用")
    for t in threads[1:]:
        t.start()
    # 给后续请求一点时间挂到共享航班上，再放行 loader
    time.sleep(0.05)
    loader.release.set()
    for t in threads:
        t.join(timeout)
        assert not t.is_alive(), "有请求线程卡住未返回"
    return results, errors


class TestErrorNotPoisoning(unittest.TestCase):
    def test_error_is_not_cached(self):
        calls = []

        def loader(key):
            calls.append(key)
            raise RuntimeError("backend timeout")

        cache = GuardCache(loader, ttl=60, capacity=8)
        for _ in range(2):
            with self.assertRaises(RuntimeError):
                cache.get("pay:1")
        self.assertEqual(calls, ["pay:1", "pay:1"])
        self.assertEqual(cache.stats()["loads"], 2)
        self.assertEqual(cache.stats()["negatives"], 0)

    def test_recovers_after_transient_error(self):
        calls = []

        def loader(key):
            calls.append(key)
            if len(calls) == 1:
                raise RuntimeError("timeout once")
            return "recovered"

        cache = GuardCache(loader, ttl=60, capacity=8)
        with self.assertRaises(RuntimeError):
            cache.get("a")
        self.assertEqual(cache.get("a"), "recovered")
        self.assertEqual(cache.get("a"), "recovered")
        self.assertEqual(len(calls), 2)


class TestConcurrentCoalescing(unittest.TestCase):
    def test_concurrent_miss_runs_single_loader(self):
        def result(key, n):
            return "snapshot"

        loader = GatedLoader(result)
        cache = GuardCache(loader, ttl=60, capacity=8)
        n = 8
        results, errors = run_concurrent(cache, "hot:cfg", n, loader)

        self.assertEqual(loader.calls, ["hot:cfg"])
        self.assertEqual(results, ["snapshot"] * n)
        self.assertTrue(all(e is None for e in errors))
        self.assertEqual(cache.stats()["loads"], 1)
        self.assertEqual(cache.stats()["misses"], n)

    def test_concurrent_not_found_shared(self):
        def result(key, n):
            raise NotFound(key)

        loader = GatedLoader(result)
        cache = GuardCache(loader, ttl=60, capacity=8)
        n = 6
        results, errors = run_concurrent(cache, "ghost", n, loader)

        self.assertEqual(len(loader.calls), 1)
        self.assertEqual(sum(isinstance(e, NotFound) for e in errors), n)
        s = cache.stats()
        self.assertEqual(s["loads"], 1)
        self.assertEqual(s["negatives"], 1)

        # 第二波直接命中负缓存
        with self.assertRaises(NotFound):
            cache.get("ghost")
        self.assertEqual(len(loader.calls), 1)

    def test_concurrent_error_shared_then_retry_reloads(self):
        def result(key, n):
            raise RuntimeError("boom")

        loader = GatedLoader(result)
        cache = GuardCache(loader, ttl=60, capacity=8)
        n = 6
        results, errors = run_concurrent(cache, "a", n, loader)

        self.assertEqual(len(loader.calls), 1)
        self.assertEqual(sum(isinstance(e, RuntimeError) for e in errors), n)
        # 异常不写缓存，下一次请求重新回源
        with self.assertRaises(RuntimeError):
            cache.get("a")
        self.assertEqual(len(loader.calls), 2)

    def test_concurrent_different_keys_still_separate(self):
        calls = []
        lock = threading.Lock()

        def loader(key):
            with lock:
                calls.append(key)
            time.sleep(0.01)
            return "v:" + key

        cache = GuardCache(loader, ttl=60, capacity=16)
        results = {}

        def worker(key):
            results[key] = cache.get(key)

        keys = ["k%d" % i for i in range(4)]
        threads = [threading.Thread(target=worker, args=(k,)) for k in keys]
        for t in threads:
            t.start()
        for t in threads:
            t.join(5.0)
        self.assertEqual(sorted(calls), keys)
        self.assertEqual(results, {k: "v:" + k for k in keys})


class TestTtlFixedAtWrite(unittest.TestCase):
    def test_hot_reads_do_not_extend_ttl(self):
        clock = FakeClock()
        calls = []

        def loader(key):
            calls.append(key)
            return "v%d" % len(calls)

        cache = GuardCache(loader, ttl=5, capacity=8, clock=clock)
        self.assertEqual(cache.get("flag"), "v1")
        for _ in range(20):
            clock.advance(1)
            cache.get("flag")
        self.assertEqual(cache.get("flag"), "v5")
        self.assertEqual(len(calls), 5)

    def test_ttl_counts_from_write_not_last_read(self):
        clock = FakeClock()
        calls = []

        def load(key):
            calls.append(clock())
            return "v%d" % len(calls)

        cache = GuardCache(load, ttl=10, capacity=8, clock=clock)
        cache.get("a")                 # t=1000 写入，t=1010 到期
        clock.advance(9)
        cache.get("a")                 # 命中，不续期
        clock.advance(1)
        cache.get("a")                 # t=1010，到期，重新回源
        self.assertEqual(calls, [1000.0, 1010.0])


class TestNegativeEvictionProtection(unittest.TestCase):
    def _loader(self, calls):
        def loader(key):
            calls.append(key)
            if key.startswith("ghost"):
                raise NotFound(key)
            return "val:" + key
        return loader

    def test_negative_survives_positive_pressure(self):
        clock = FakeClock()
        calls = []
        cache = GuardCache(self._loader(calls), ttl=60, capacity=2,
                           negative_ttl=600, clock=clock)
        with self.assertRaises(NotFound):
            cache.get("ghost")
        cache.get("k1")
        cache.get("k2")
        cache.get("k3")
        cache.get("k4")
        with self.assertRaises(NotFound):
            cache.get("ghost")
        self.assertEqual(calls.count("ghost"), 1)

    def test_oldest_negative_evicted_when_all_negative(self):
        clock = FakeClock()
        calls = []
        cache = GuardCache(self._loader(calls), ttl=60, capacity=2,
                           negative_ttl=600, clock=clock)
        for key in ("ghost1", "ghost2", "ghost3"):
            with self.assertRaises(NotFound):
                cache.get(key)
        self.assertEqual(cache.stats()["evicted"], 1)
        # 全是负条目时才退回到 LRU：最旧的 ghost1 被挤掉
        with self.assertRaises(NotFound):
            cache.get("ghost1")
        self.assertEqual(calls.count("ghost1"), 2)
        with self.assertRaises(NotFound):
            cache.get("ghost3")
        self.assertEqual(calls.count("ghost3"), 1)


if __name__ == "__main__":
    unittest.main()
