"""多线程行为测试：分区对拍、容量压测、吞吐底线、回调重入。

不碰 tests/ 里已有的基线，这里只加新用例。
"""

import random
import threading
import time
import unittest

import support  # noqa: F401  先挂 sys.path

from lruvault import LRUCache
from lruvault.reference import PlainLRU, apply_ops, random_ops

THREADS = 8
KEY_SPACE = 64
OPS_PER_THREAD = 2000


def remap(ops, offset):
    """把操作序列的键整体平移一段，给每个线程划出独立的键空间。"""
    return [(kind, key + offset, value) for kind, key, value in ops]


def run_threads(bodies):
    """同时放一批线程跑，返回线程里抛出的异常列表。"""
    errors = []
    barrier = threading.Barrier(len(bodies))

    def wrap(body):
        def target():
            barrier.wait()
            try:
                body()
            except Exception as exc:  # pragma: no cover - 失败时一并报出
                errors.append(exc)
        return threading.Thread(target=target)

    threads = [wrap(body) for body in bodies]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return errors


class DisjointKeySpaceParityTest(unittest.TestCase):
    """八线程各占一段键空间随机增删查，容量足够大不触发淘汰。

    跑完每个键的值、同线程键的新旧次序、每个 get 的返回值、
    汇总计数都要和逐线程串行回放的参考实现一致。
    """

    def test_thread_segments_match_reference(self):
        capacity = THREADS * KEY_SPACE
        plans = [remap(random_ops(500 + tid, OPS_PER_THREAD, KEY_SPACE),
                       tid * KEY_SPACE)
                 for tid in range(THREADS)]
        cache = LRUCache(capacity=capacity)
        results = [None] * THREADS
        sentinels = [object() for _ in range(THREADS)]

        def make_body(tid):
            def body():
                results[tid] = apply_ops(cache, plans[tid],
                                         default=sentinels[tid])
            return body

        errors = run_threads([make_body(tid) for tid in range(THREADS)])
        self.assertEqual(errors, [])

        cache_order = cache.keys()
        cache_values = dict(cache.snapshot())
        totals = {"hits": 0, "misses": 0, "evictions": 0,
                  "puts": 0, "deletes": 0, "live": 0}
        for tid in range(THREADS):
            offset = tid * KEY_SPACE
            mine = set(range(offset, offset + KEY_SPACE))
            ref = PlainLRU(capacity=capacity)
            want_results = apply_ops(ref, plans[tid], default=sentinels[tid])
            self.assertEqual(results[tid], want_results,
                             "线程 %d 的 get 返回值与参考不一致" % tid)
            self.assertEqual([key for key in cache_order if key in mine],
                             ref.keys(),
                             "线程 %d 的键新旧次序与参考不一致" % tid)
            for key, value in ref.snapshot():
                self.assertEqual(cache_values.get(key), value,
                                 "键 %r 的最终值与参考不一致" % (key,))
            stats = ref.stats()
            for field in totals:
                totals[field] += getattr(stats, field)

        stats = cache.stats()
        for field, want in totals.items():
            self.assertEqual(getattr(stats, field), want,
                             "汇总计数 %s 与参考不一致" % field)


class SerialCapacityPressureTest(unittest.TestCase):
    """串行灌键压容量：谁被踢、踢的顺序、最终状态都和参考一致。"""

    def test_eviction_sequence_matches_reference(self):
        ops = random_ops(900, 600, key_space=40)
        seen = {}
        for name, cls in (("cache", LRUCache), ("ref", PlainLRU)):
            evicted = []
            target = cls(capacity=12,
                         on_evict=lambda k, v: evicted.append((k, v)))
            apply_ops(target, ops)
            seen[name] = (evicted, target.keys(), target.snapshot(),
                          tuple(target.stats()))
        self.assertEqual(seen["cache"], seen["ref"])
        self.assertGreater(len(seen["cache"][0]), 0, "这段序列该有淘汰发生")


class SizeSamplingTest(unittest.TestCase):
    """压测期间高频采样 size：任何时候都不许越过 capacity。"""

    def test_size_never_exceeds_capacity(self):
        capacity = 32
        cache = LRUCache(capacity=capacity)
        stop = time.monotonic() + 0.6

        def worker(seed, deadline):
            rng = random.Random(seed)
            while time.monotonic() < deadline:
                key = rng.randrange(128)
                roll = rng.random()
                if roll < 0.6:
                    cache.get(key)
                elif roll < 0.9:
                    cache.put(key, "v%d" % key)
                else:
                    cache.delete(key)

        threads = [threading.Thread(target=worker, args=(2000 + i, stop))
                   for i in range(4)]
        for thread in threads:
            thread.start()
        violations = []
        while time.monotonic() < stop:
            size = cache.size()
            if size > capacity:
                violations.append(size)
        for thread in threads:
            thread.join()
        self.assertEqual(violations, [])
        self.assertEqual(cache.size(), len(cache.keys()))
        self.assertEqual(cache.size(), cache.stats().live)
        self.assertLessEqual(cache.size(), capacity)


class ThroughputTest(unittest.TestCase):
    """八线程读多写少的总吞吐不许掉到单线程参考的一成以下。"""

    DURATION = 0.5

    def mixed_load(self, target, rng, deadline, counter):
        while time.monotonic() < deadline:
            key = rng.randrange(512)
            if rng.random() < 0.9:
                target.get(key)
            else:
                target.put(key, key)
            counter[0] += 1

    def test_throughput_floor(self):
        ref = PlainLRU(capacity=256)
        ref_count = [0]
        self.mixed_load(ref, random.Random(7),
                        time.monotonic() + self.DURATION, ref_count)

        cache = LRUCache(capacity=256)
        deadline = time.monotonic() + self.DURATION
        counts = [[0] for _ in range(THREADS)]

        def make_body(tid):
            def body():
                self.mixed_load(cache, random.Random(100 + tid),
                                deadline, counts[tid])
            return body

        errors = run_threads([make_body(tid) for tid in range(THREADS)])
        self.assertEqual(errors, [])
        total = sum(count[0] for count in counts)
        self.assertGreaterEqual(total * 10, ref_count[0],
                                "总吞吐 %d 掉到参考 %d 的一成以下"
                                % (total, ref_count[0]))


class ReentrantCallbackTest(unittest.TestCase):
    """淘汰回调里再增删查不许死锁；回调抛错后缓存照常能用。"""

    def test_callback_may_reenter_cache(self):
        fired = []
        state = {"inserted": False}

        def on_evict(key, value):
            fired.append((key, value))
            cache.get("probe")
            cache.delete("probe")
            if not state["inserted"]:
                state["inserted"] = True
                cache.put("probe", "p")

        cache = LRUCache(capacity=2, on_evict=on_evict)
        cache.put("a", 1)
        cache.put("b", 2)

        done = []

        def trigger():
            cache.put("c", 3)
            done.append(True)

        thread = threading.Thread(target=trigger)
        thread.start()
        thread.join(timeout=5.0)
        self.assertFalse(thread.is_alive(), "回调重入把 worker 卡死了")
        self.assertEqual(done, [True])
        self.assertTrue(fired, "淘汰回调该至少触发一次")
        self.assertEqual(cache.size(), len(cache.keys()))
        self.assertLessEqual(cache.size(), cache.capacity)

    def test_callback_error_leaves_cache_usable(self):
        calls = []

        def on_evict(key, value):
            calls.append((key, value))
            if len(calls) == 1:
                raise RuntimeError("回调炸了")

        cache = LRUCache(capacity=1, on_evict=on_evict)
        cache.put("a", 1)
        with self.assertRaises(RuntimeError):
            cache.put("b", 2)
        self.assertEqual(calls, [("a", 1)])
        # 缓存没锁死、状态自洽，后续读写照常
        self.assertEqual(cache.get("b"), 2)
        cache.put("c", 3)
        self.assertEqual(calls, [("a", 1), ("b", 2)])
        self.assertEqual(cache.keys(), ["c"])
        self.assertEqual(cache.size(), len(cache.keys()))
        self.assertLessEqual(cache.size(), cache.capacity)


if __name__ == "__main__":
    unittest.main()
