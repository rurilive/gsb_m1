"""防回归测试：失败不粘连、失败不阻塞、过期合并、跟随者结果一致。"""
import threading
import time
import unittest

from sfcache import Cache


class FakeClock:
    def __init__(self, start=1000.0):
        self.now = float(start)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def run_concurrent(cache, key, n, timeout=5.0):
    """n 个线程同时 get(key)，返回 (results, errors)，并断言无人卡死。"""
    results = [None] * n
    errors = [None] * n

    def worker(i):
        try:
            results[i] = cache.get(key)
        except Exception as exc:  # noqa: BLE001 - 测试需要收集异常
            errors[i] = exc

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout)
    stuck = [t for t in threads if t.is_alive()]
    assert not stuck, "%d 个线程在 %.1fs 内没有返回" % (len(stuck), timeout)
    return results, errors


class TestFailureNotSticky(unittest.TestCase):
    def test_failed_key_recovers_on_next_get(self):
        """回源失败一次后，下一个请求应重新回源而不是重抛旧异常。"""
        calls = []

        def loader(key):
            calls.append(key)
            if len(calls) == 1:
                raise TimeoutError("backend flapped")
            return "recovered"

        cache = Cache(loader, ttl=None)
        with self.assertRaises(TimeoutError):
            cache.get("k")
        self.assertEqual(cache.get("k"), "recovered")
        self.assertEqual(calls, ["k", "k"])

    def test_failure_of_one_key_does_not_affect_others(self):
        def loader(key):
            if key == "bad":
                raise ValueError("boom")
            return "ok:%s" % key

        cache = Cache(loader, ttl=None)
        with self.assertRaises(ValueError):
            cache.get("bad")
        self.assertEqual(cache.get("good"), "ok:good")

    def test_invalidate_after_failure_allows_reload(self):
        calls = []

        def loader(key):
            calls.append(key)
            if len(calls) == 1:
                raise RuntimeError("flap")
            return "v2"

        cache = Cache(loader, ttl=None)
        with self.assertRaises(RuntimeError):
            cache.get("k")
        cache.invalidate("k")
        self.assertEqual(cache.get("k"), "v2")


class TestFailureDoesNotBlockFollowers(unittest.TestCase):
    def test_concurrent_failure_releases_all_waiters(self):
        """回源抛异常时，所有合并的跟随者都应及时拿到异常，而不是挂死。"""
        entered = threading.Event()
        release = threading.Event()
        calls = []

        def loader(key):
            calls.append(key)
            entered.set()
            release.wait(5.0)
            raise TimeoutError("backend down")

        cache = Cache(loader, ttl=None)
        n = 8
        results = [None] * n
        errors = [None] * n

        def worker(i):
            try:
                results[i] = cache.get("hot")
            except Exception as exc:  # noqa: BLE001
                errors[i] = exc

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        self.assertTrue(entered.wait(5.0), "回源没有被触发")
        time.sleep(0.1)  # 等其余线程都进入等待
        release.set()
        for t in threads:
            t.join(5.0)
        for t in threads:
            self.assertFalse(t.is_alive(), "有线程被失败卡死")

        self.assertEqual(calls, ["hot"])
        for exc in errors:
            self.assertIsInstance(exc, TimeoutError)


class TestExpiredKeySingleflight(unittest.TestCase):
    def test_expired_entry_concurrent_reload_merges(self):
        """条目过期后并发到达，仍只回源一次。"""
        clock = FakeClock()
        entered = threading.Event()
        release = threading.Event()
        calls = []

        def loader(key):
            calls.append(key)
            if len(calls) > 1:
                entered.set()
                release.wait(5.0)
            return "v%d" % len(calls)

        cache = Cache(loader, ttl=60, clock=clock)
        self.assertEqual(cache.get("hot"), "v1")
        clock.advance(61)

        n = 8
        results = [None] * n
        errors = [None] * n

        def worker(i):
            try:
                results[i] = cache.get("hot")
            except Exception as exc:  # noqa: BLE001
                errors[i] = exc

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        self.assertTrue(entered.wait(5.0), "过期后没有触发重新回源")
        time.sleep(0.1)  # 等其余线程都进入等待
        release.set()
        for t in threads:
            t.join(5.0)
        for t in threads:
            self.assertFalse(t.is_alive())

        self.assertEqual(calls, ["hot", "hot"])
        self.assertEqual(cache.loads, 2)
        self.assertEqual(results, ["v2"] * n)
        self.assertEqual(errors, [None] * n)


class TestFollowersGetLeaderValue(unittest.TestCase):
    def test_all_waiters_receive_the_loaded_value(self):
        """同一批并发请求必须全部拿到本轮加载出的值。"""
        entered = threading.Event()
        release = threading.Event()

        def loader(key):
            entered.set()
            release.wait(5.0)
            return "round-value"

        cache = Cache(loader, ttl=None)
        n = 16
        results = [None] * n
        errors = [None] * n

        def worker(i):
            try:
                results[i] = cache.get("hot")
            except Exception as exc:  # noqa: BLE001
                errors[i] = exc

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        self.assertTrue(entered.wait(5.0))
        time.sleep(0.1)
        release.set()
        for t in threads:
            t.join(5.0)

        self.assertEqual(results, ["round-value"] * n)
        self.assertEqual(errors, [None] * n)


if __name__ == "__main__":
    unittest.main()
