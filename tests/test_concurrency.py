"""多线程场景测试：并发对拍、容量压测、吞吐底线、可重入回调。"""

import random
import threading
import time
import unittest

import support  # noqa: F401  先挂 sys.path

from lruvault import LRUCache
from lruvault.reference import PlainLRU, random_ops

SENTINEL = object()


class DisjointKeySpaceParityTest(unittest.TestCase):
    """八线程各占一段键空间随机增删查，跑完逐键对拍参考实现。"""

    THREADS = 8
    KEY_SPACE = 16
    OPS_PER_THREAD = 300
    CAPACITY = 256  # 装得下全部键，排除淘汰带来的时序不确定

    def run_cache(self):
        cache = LRUCache(capacity=self.CAPACITY)
        ops_per_thread = [
            random_ops(seed=900 + tid, count=self.OPS_PER_THREAD,
                       key_space=self.KEY_SPACE)
            for tid in range(self.THREADS)
        ]
        results = [[] for _ in range(self.THREADS)]
        errors = []

        def work(tid):
            base = tid * self.KEY_SPACE
            try:
                for kind, key, value in ops_per_thread[tid]:
                    if kind == "get":
                        results[tid].append(cache.get(base + key, SENTINEL))
                    elif kind == "put":
                        cache.put(base + key, value)
                    else:
                        cache.delete(base + key)
            except Exception as exc:  # 汇总后统一断言，保留现场
                errors.append(exc)

        threads = [threading.Thread(target=work, args=(tid,))
                   for tid in range(self.THREADS)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        return cache, ops_per_thread, results

    def test_disjoint_key_spaces_match_reference(self):
        cache, ops_per_thread, results = self.run_cache()
        cache_snapshot = dict(cache.snapshot())
        cache_keys = cache.keys()
        for tid in range(self.THREADS):
            base = tid * self.KEY_SPACE
            ref = PlainLRU(capacity=self.CAPACITY)
            want_results = []
            for kind, key, value in ops_per_thread[tid]:
                if kind == "get":
                    want_results.append(ref.get(base + key, SENTINEL))
                elif kind == "put":
                    ref.put(base + key, value)
                else:
                    ref.delete(base + key)
            with self.subTest(thread=tid):
                self.assertEqual(results[tid], want_results)
                # 每个键的最终值与参考一致
                ref_snapshot = dict(ref.snapshot())
                for key, want in ref_snapshot.items():
                    self.assertEqual(cache_snapshot.get(key, SENTINEL), want)
                # 同线程键的新旧次序与参考逐条一致
                segment = [key for key in cache_keys
                           if base <= key < base + self.KEY_SPACE]
                self.assertEqual(segment, ref.keys())


class SerialFloodParityTest(unittest.TestCase):
    """串行灌键压容量，淘汰序列与参考逐条一致。"""

    def test_flood_eviction_matches_reference(self):
        capacity = 8
        evicted = {"cache": [], "ref": []}
        cache = LRUCache(capacity=capacity,
                         on_evict=lambda k, v: evicted["cache"].append((k, v)))
        ref = PlainLRU(capacity=capacity,
                       on_evict=lambda k, v: evicted["ref"].append((k, v)))
        for index in range(200):
            cache.put("k%d" % index, index)
            ref.put("k%d" % index, index)
            if index % 7 == 3:  # 隔几手摸一下旧键，搅动新旧次序
                key = "k%d" % (index // 2)
                self.assertEqual(cache.get(key, SENTINEL),
                                 ref.get(key, SENTINEL))
        self.assertEqual(evicted["cache"], evicted["ref"])
        self.assertEqual(cache.keys(), ref.keys())
        self.assertEqual(cache.snapshot(), ref.snapshot())
        self.assertEqual(tuple(cache.stats()), tuple(ref.stats()))
        self.assertLessEqual(cache.size(), capacity)


class CapacityPressureTest(unittest.TestCase):
    """压测期间高频采样 size，不许越过 capacity，结构不许散。"""

    def test_size_never_exceeds_capacity_under_pressure(self):
        capacity = 32
        cache = LRUCache(capacity=capacity)
        stop = threading.Event()
        errors = []

        def work(seed):
            rng = random.Random(seed)
            while not stop.is_set():
                key = rng.randrange(128)
                roll = rng.random()
                try:
                    if roll < 0.5:
                        cache.get(key, SENTINEL)
                    elif roll < 0.85:
                        cache.put(key, "v%d" % key)
                    else:
                        cache.delete(key)
                except Exception as exc:
                    errors.append(exc)
                    stop.set()

        threads = [threading.Thread(target=work, args=(5000 + i,))
                   for i in range(4)]
        for thread in threads:
            thread.start()
        peak = 0
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            peak = max(peak, cache.size())
        stop.set()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        self.assertLessEqual(peak, capacity)
        # 压完之后 dict、链表、计数三者必须对齐
        keys = cache.keys()
        self.assertEqual(cache.size(), len(keys))
        self.assertEqual(cache.stats().live, len(keys))
        self.assertEqual([key for key, _ in cache.snapshot()], keys)
        self.assertEqual(len(keys), len(set(keys)))


class ThroughputTest(unittest.TestCase):
    """八线程读多写少，总吞吐不许掉到单线程参考的一成以下。"""

    THREADS = 8
    OPS_PER_THREAD = 40000
    KEY_SPACE = 64

    def _replay(self, target, seed, count):
        rng = random.Random(seed)
        for _ in range(count):
            key = rng.randrange(self.KEY_SPACE)
            if rng.random() < 0.9:
                target.get(key, SENTINEL)
            else:
                target.put(key, key)

    def test_read_heavy_throughput_floor(self):
        total = self.THREADS * self.OPS_PER_THREAD

        ref = PlainLRU(capacity=self.KEY_SPACE * 2)
        for key in range(self.KEY_SPACE):
            ref.put(key, key)
        start = time.perf_counter()
        self._replay(ref, seed=1, count=total)
        ref_rate = total / (time.perf_counter() - start)

        cache = LRUCache(capacity=self.KEY_SPACE * 2)
        for key in range(self.KEY_SPACE):
            cache.put(key, key)
        threads = [threading.Thread(target=self._replay,
                                    args=(cache, 100 + i,
                                          self.OPS_PER_THREAD))
                   for i in range(self.THREADS)]
        start = time.perf_counter()
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        cache_rate = total / (time.perf_counter() - start)

        self.assertGreaterEqual(
            cache_rate, ref_rate / 10,
            "八线程总吞吐 %.0f ops/s 掉到参考 %.0f ops/s 的一成以下"
            % (cache_rate, ref_rate))


class ReentrantCallbackTest(unittest.TestCase):
    """淘汰回调里再增删查不许死锁；回调抛错缓存也得能用。"""

    def test_callback_can_reenter_the_cache(self):
        fired = []
        holder = {}
        depth = {"n": 0}

        def on_evict(key, value):
            fired.append((key, value))
            cache = holder["cache"]
            cache.get("probe")          # 查
            cache.delete("probe")       # 删
            if depth["n"] < 3:          # 增（限制递归深度）
                depth["n"] += 1
                cache.put("probe", "p")
                depth["n"] -= 1

        cache = LRUCache(capacity=2, on_evict=on_evict)
        holder["cache"] = cache
        cache.put("a", 1)
        cache.put("b", 2)

        done = []
        thread = threading.Thread(
            target=lambda: (cache.put("c", 3), done.append(True)))
        thread.start()
        thread.join(timeout=5.0)
        self.assertFalse(thread.is_alive(), "回调重入把 worker 卡死了")
        self.assertEqual(done, [True])
        self.assertTrue(fired)
        # 回调闹完之后缓存本身还是自洽的
        keys = cache.keys()
        self.assertEqual(cache.size(), len(keys))
        self.assertLessEqual(cache.size(), cache.capacity)

    def test_callback_exception_propagates_and_cache_survives(self):
        fired = []

        def on_evict(key, value):
            fired.append((key, value))
            if len(fired) == 1:
                raise RuntimeError("回调炸了")

        cache = LRUCache(capacity=1, on_evict=on_evict)
        cache.put("a", 1)
        with self.assertRaises(RuntimeError):
            cache.put("b", 2)
        # 抛错之后缓存结构没坏，还能正常用
        self.assertEqual(cache.size(), 1)
        self.assertEqual(cache.get("b"), 2)
        self.assertEqual(cache.keys(), ["b"])
        cache.put("c", 3)  # 第二次淘汰回调不再抛
        self.assertEqual(fired, [("a", 1), ("b", 2)])
        self.assertEqual(cache.keys(), ["c"])
        stats = cache.stats()
        self.assertEqual((stats.evictions, stats.live), (2, 1))


if __name__ == "__main__":
    unittest.main()
