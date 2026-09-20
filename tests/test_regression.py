"""sfcache 缺陷修复的防回归测试。

对应三个线上现象：
1. 回源抖了一次之后，该 key 之后一直直接报错（失败被永久固化）。
2. 失败那一趟的并发跟随者永远不返回，数量等于并发数（线程池被占满）。
3. 热门 key 高峰期回源次数翻几倍，少数请求拿到的不是本轮结果
   （过期分支不注册 flight；结果在 done 置位之后才发布）。
"""
import threading
import time
import unittest

import sfcache.cache as cache_mod
from sfcache import Cache


class FakeClock:
    def __init__(self, start=1000.0):
        self.now = float(start)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class FlakyLoader:
    """前 fail_times 次抛异常，之后返回带调用序号的值。"""

    def __init__(self, fail_times=1, exc_cls=RuntimeError):
        self.calls = 0
        self.lock = threading.Lock()
        self._fail_times = fail_times
        self._exc_cls = exc_cls

    def __call__(self, key):
        with self.lock:
            self.calls += 1
            seq = self.calls
            if seq <= self._fail_times:
                raise self._exc_cls("backend timeout #%d" % seq)
        time.sleep(0.01)
        return "%s-v%d" % (key, seq)


class TestFailureNotSticky(unittest.TestCase):
    """现象 1：一次回源超时不应让该 key 永久报错。"""

    def test_retry_after_transient_failure_succeeds(self):
        loader = FlakyLoader(fail_times=1)
        cache = Cache(loader, ttl=None)
        with self.assertRaises(RuntimeError):
            cache.get("k")
        # 旧实现这里会再次抛同一个异常且不再回源
        self.assertEqual(cache.get("k"), "k-v2")
        self.assertEqual(loader.calls, 2)

    def test_failure_does_not_poison_other_keys(self):
        loader = FlakyLoader(fail_times=1)
        cache = Cache(loader, ttl=None)
        with self.assertRaises(RuntimeError):
            cache.get("bad")
        self.assertEqual(cache.get("good"), "good-v2")

    def test_repeated_failures_keep_retrying(self):
        loader = FlakyLoader(fail_times=3)
        cache = Cache(loader, ttl=None)
        for _ in range(3):
            with self.assertRaises(RuntimeError):
                cache.get("k")
        self.assertEqual(cache.get("k"), "k-v4")
        self.assertEqual(loader.calls, 4)


class TestFailedFlightReleasesWaiters(unittest.TestCase):
    """现象 2：失败那一趟的并发跟随者必须全部拿到异常并返回，不许挂住。"""

    def test_all_concurrent_waiters_raise_and_return(self):
        entered = threading.Event()
        release = threading.Event()

        def loader(key):
            entered.set()
            release.wait(5.0)
            raise IOError("backend timeout")

        cache = Cache(loader, ttl=None)
        n = 8
        errors = [None] * n

        def worker(i):
            try:
                cache.get("k")
            except Exception as exc:
                errors[i] = exc

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        self.assertTrue(entered.wait(5.0))
        time.sleep(0.1)  # 等其余线程都挂到同一趟 flight 上
        release.set()
        for t in threads:
            t.join(5.0)

        self.assertFalse(any(t.is_alive() for t in threads), "有跟随者永久挂住")
        self.assertEqual(sum(1 for e in errors if isinstance(e, IOError)), n)

        # 失败的 flight 必须已摘除，下一次请求能发起新回源
        def good_loader(key):
            return "recovered"

        cache._loader = good_loader
        self.assertEqual(cache.get("k"), "recovered")


class TestExpiredEntrySingleflight(unittest.TestCase):
    """现象 3a：过期 key 上的并发请求也必须合并成一次回源。"""

    def test_concurrent_get_after_expiry_merges(self):
        clock = FakeClock()
        calls = []

        def initial_loader(key):
            calls.append(key)
            return "old-value"

        cache = Cache(initial_loader, ttl=60, clock=clock)
        self.assertEqual(cache.get("k"), "old-value")
        self.assertEqual(calls, ["k"])

        entered = threading.Event()
        release = threading.Event()

        def reload_loader(key):
            calls.append(key)
            entered.set()
            release.wait(5.0)
            return "fresh-value"

        cache._loader = reload_loader
        clock.advance(61)  # 条目过期

        n = 8
        results = [None] * n
        errors = [None] * n

        def worker(i):
            try:
                results[i] = cache.get("k")
            except Exception as exc:
                errors[i] = exc

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        self.assertTrue(entered.wait(5.0))
        time.sleep(0.1)
        release.set()
        for t in threads:
            t.join(5.0)

        self.assertFalse(any(t.is_alive() for t in threads))
        self.assertEqual(calls, ["k", "k"], "过期后的并发回源没有被合并")
        self.assertEqual([r for r in results if r is not None], ["fresh-value"] * n)
        self.assertTrue(all(e is None for e in errors))

        # 新结果已落缓存，TTL 内不再回源
        self.assertEqual(cache.get("k"), "fresh-value")
        self.assertEqual(len(calls), 2)


class TestFlightResultPublishedBeforeSignal(unittest.TestCase):
    """现象 3b：跟随者醒来时必须拿到本轮结果，不允许拿到 None/上一轮旧值。"""

    def test_result_is_published_before_done_is_set(self):
        # 放大“先发信号、后写结果”的调度窗口：done.set() 唤醒等待者后故意
        # 逗留 100ms。若实现先 set() 再写 value，跟随者必然在这段时间读到
        # 尚未发布的 None；正确实现先写 value 再 set()，不受影响。
        class SlowSetEvent(threading.Event):
            def set(self):
                super().set()
                time.sleep(0.1)

        class SlowFlight:
            __slots__ = ("done", "value", "error")

            def __init__(self):
                self.done = SlowSetEvent()
                self.value = None
                self.error = None

        entered = threading.Event()
        release = threading.Event()

        def loader(key):
            entered.set()
            release.wait(5.0)
            return "fresh-value"

        cache = Cache(loader, ttl=None)
        original_flight = cache_mod._Flight
        cache_mod._Flight = SlowFlight
        try:
            n = 8
            barrier = threading.Barrier(n)
            results = [None] * n

            def worker(i):
                barrier.wait()
                results[i] = cache.get("hot")

            threads = [
                threading.Thread(target=worker, args=(i,)) for i in range(n)
            ]
            for t in threads:
                t.start()
            self.assertTrue(entered.wait(5.0))
            time.sleep(0.1)  # 等所有跟随者挂到这一趟 flight 上
            release.set()
            for t in threads:
                t.join(5.0)
        finally:
            cache_mod._Flight = original_flight

        self.assertFalse(any(t.is_alive() for t in threads))
        self.assertEqual(
            results,
            ["fresh-value"] * n,
            "有跟随者读到了信号发布前的 value（None/旧值）",
        )


if __name__ == "__main__":
    unittest.main()
