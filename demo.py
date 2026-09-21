"""lruvault 现状演示：单线程用法先走一遍，再把值班撞到的几个现场摆出来。

带“期望”字样的行是修好之后该有的样子，跑在现在的代码上未必对得上。
压测段自己缩短线程切换间隔，几秒钟就能撞出问题。
"""

import random
import sys
import threading
import time

from lruvault import LRUCache

SENTINEL = object()
KEY_SPACE = 128
RUN_SECONDS = 1.2


def basic_walkthrough():
    print("=== 场景一：单线程基本用法 ===")
    evicted = []
    cache = LRUCache(capacity=3, on_evict=lambda k, v: evicted.append((k, v)))
    for key in "abcd":
        cache.put(key, key.upper())
    cache.get("b")
    stats = cache.stats()
    print("   键从新到旧: %s，快照 %s" % (cache.keys(), cache.snapshot()))
    print("   命中 %d 未中 %d 淘汰 %d 当前 %d 命中率 %.2f，淘汰记录 %s"
          % (stats.hits, stats.misses, stats.evictions, stats.live,
             cache.hit_rate(), evicted))


def worker(cache, seed, deadline, tally):
    rng = random.Random(seed)
    while time.monotonic() < deadline:
        key = rng.randrange(KEY_SPACE)
        roll = rng.random()
        try:
            if roll < 0.6:
                value = cache.get(key, SENTINEL)
                if value is None or (value is not SENTINEL
                                     and value != "v%d" % key):
                    tally["bad_get"] += 1
            elif roll < 0.9:
                cache.put(key, "v%d" % key)
            else:
                cache.delete(key)
        except Exception:
            tally["errors"] += 1


def pressure_run():
    print("=== 场景二：多线程压一会儿，旁边一直采样 ===")
    cache = LRUCache(capacity=32)
    tally = {"bad_get": 0, "errors": 0}
    stop = time.monotonic() + RUN_SECONDS
    peak = over = gap = samples = 0

    previous = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        threads = [threading.Thread(target=worker,
                                    args=(cache, 1000 + i, stop, tally),
                                    daemon=True)
                   for i in range(4)]
        for thread in threads:
            thread.start()
        while time.monotonic() < stop:
            samples += 1
            size = cache.size()
            peak = max(peak, size)
            if size > cache.capacity:
                over += 1
            if samples % 256 == 0:
                gap = max(gap, size - len(cache.keys()))
        for thread in threads:
            thread.join()
    finally:
        sys.setswitchinterval(previous)

    print("   采样 %d 次，size 峰值 %d，capacity %d，越界 %d 次"
          % (samples, peak, cache.capacity, over))
    print("   期望：峰值不超 capacity，越界 0 次")
    print("   采样中 size 与 keys 的最大差值 %d；压完 size=%d，keys=%d，live=%d"
          % (gap, cache.size(), len(cache.keys()), cache.stats().live))
    print("   期望：三个数一样大，差值为 0")
    print("   get 拿回失效值 %d 次，线程出错 %d 次；期望：都是 0"
          % (tally["bad_get"], tally["errors"]))


def put_stats():
    print("=== 场景三：同 key 并发 put 之后看命中率 ===")
    cache = LRUCache(capacity=16)
    workers, rounds = 8, 3000
    barrier = threading.Barrier(workers)

    def writer(tid):
        for index in range(rounds):
            barrier.wait()
            cache.put(index, "v%d" % tid)

    previous = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        threads = [threading.Thread(target=writer, args=(i,), daemon=True)
                   for i in range(workers)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    finally:
        sys.setswitchinterval(previous)

    stats = cache.stats()
    print("   %d 个线程各 %d 轮 put，hits=%d，puts=%d，命中率 %.4f"
          % (workers, rounds, stats.hits, stats.puts, cache.hit_rate()))
    print("   期望：hits 是 0，命中率 0.0000")


def reentrant_callback():
    print("=== 场景四：淘汰回调里顺手查一下缓存 ===")
    holder = {}
    fired = []

    def on_evict(key, value):
        fired.append((key, value))
        holder["cache"].get("probe")

    cache = LRUCache(capacity=1, on_evict=on_evict)
    holder["cache"] = cache
    cache.put("a", "A")
    thread = threading.Thread(target=lambda: cache.put("b", "B"), daemon=True)
    thread.start()
    thread.join(timeout=1.0)
    if thread.is_alive():
        print("   一秒内没回来，回调里的 get 卡住了")
    else:
        print("   跑完了，回调记录: %s" % (fired,))
    print("   期望：跑得完，回调里增删查都正常")


def main():
    basic_walkthrough()
    pressure_run()
    put_stats()
    reentrant_callback()


if __name__ == "__main__":
    main()
