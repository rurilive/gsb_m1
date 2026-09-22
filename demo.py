"""resolvcache 现状演示。

第一段：命中、过期与上游失败。
第二段：多个线程同时查同一个域名，数一数上游被打了几次。
第三段：预留的新行为演示位子（见文末注释）。
第四段：跟直连上游对拍，看随机序列下的返回与上游调用数。
"""

import random
import threading
import time

from resolvcache.cache import ResolverCache
from resolvcache.clock import ManualClock
from resolvcache.refcheck import run_diff
from resolvcache.upstream import FakeUpstream, UpstreamError


def show_hit_and_expiry():
    print("=== 命中 / 过期 / 上游失败 ===")
    upstream = FakeUpstream({
        "api.svc.internal": ("10.0.0.10", 20.0),
        "cdn.svc.internal": ("10.0.0.20", 60.0),
    })
    clock = ManualClock(1000.0)
    cache = ResolverCache(upstream, clock=clock)

    print("  lookup(api) ->", cache.lookup("api.svc.internal"))
    print("  lookup(api) 再来一次 ->", cache.lookup("api.svc.internal"))
    print("  上游调用数:", upstream.stats()["calls"])
    clock.advance(25.0)
    print("  时钟推进 25 秒后再查 ->", cache.lookup("api.svc.internal"))
    print("  上游调用数:", upstream.stats()["calls"])
    upstream.set_failing("cdn.svc.internal")
    try:
        cache.lookup("cdn.svc.internal")
    except UpstreamError as exc:
        print("  上游挂了:", exc)
    print("  缓存计数:", cache.stats())


def show_concurrent_same_name():
    print("=== 并发查同一个域名 ===")
    upstream = FakeUpstream({"hot.svc.internal": ("10.0.0.30", 60.0)},
                            delay=0.02)
    cache = ResolverCache(upstream, clock=ManualClock(2000.0))
    results = []
    lock = threading.Lock()

    def worker():
        address = cache.lookup("hot.svc.internal")
        with lock:
            results.append(address)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    print("  8 个线程都拿到:", set(results))
    print("  上游调用数:", upstream.stats()["calls"])


def show_negative_cache():
    print("=== 负缓存：失败域名短期不再回源 ===")
    upstream = FakeUpstream({})
    clock = ManualClock(3000.0)
    cache = ResolverCache(upstream, clock=clock, negative_ttl=5.0)
    for _ in range(3):
        try:
            cache.lookup("dead.svc.internal")
        except UpstreamError:
            pass
    print("  连查 3 次失败域名，上游调用数:", upstream.stats()["calls"])
    clock.advance(4.0)
    try:
        cache.lookup("dead.svc.internal")
    except UpstreamError:
        pass
    print("  4 秒后再查（负缓存未到期），上游调用数:",
          upstream.stats()["calls"])
    clock.advance(1.0)
    upstream.set_record("dead.svc.internal", "10.1.1.1", 30.0)
    print("  到点后域名恢复，再查 ->",
          cache.lookup("dead.svc.internal"))
    print("  上游调用数:", upstream.stats()["calls"])


def show_single_flight_failure_broadcast():
    print("=== single-flight：并发只放一个，失败全员广播 ===")
    upstream = FakeUpstream({"hot.svc.internal": ("10.0.0.40", 60.0)},
                            delay=0.05)
    cache = ResolverCache(upstream, clock=ManualClock(4000.0))
    results = []
    result_lock = threading.Lock()

    def worker():
        result = cache.lookup("hot.svc.internal")
        with result_lock:
            results.append(result)

    threads = [threading.Thread(target=worker) for _ in range(12)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    print("  12 线程并发 miss，上游调用数:", upstream.stats()["calls"],
          "峰值在飞:", upstream.stats()["peak_in_flight"])
    print("  全员拿到:", set(results))

    fail_upstream = FakeUpstream({}, delay=0.05)
    fail_cache = ResolverCache(fail_upstream, clock=ManualClock(4100.0),
                               negative_ttl=5.0)
    errors = []
    error_lock = threading.Lock()

    def fail_worker():
        try:
            fail_cache.lookup("missing.svc.internal")
        except UpstreamError as exc:
            with error_lock:
                errors.append(exc)

    threads = [threading.Thread(target=fail_worker) for _ in range(12)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    print("  上游抖动 12 线程并发失败：拿到错的人数 =", len(errors),
          "上游调用数 =", fail_upstream.stats()["calls"])


def show_background_refresh_and_jitter():
    print("=== 半程预刷新：旧值顶着，后台换血，失败顶到硬过期 ===")
    upstream = FakeUpstream({"api.svc.internal": ("10.0.0.1", 20.0)})
    clock = ManualClock(5000.0)
    cache = ResolverCache(upstream, clock=clock, jitter=0.0)
    print("  首次解析 ->", cache.lookup("api.svc.internal"))
    upstream.set_record("api.svc.internal", "10.0.0.2", 20.0)
    clock.advance(10.0)  # TTL 过半
    print("  过半那一查先拿旧值 ->", cache.lookup("api.svc.internal"),
          "上游调用数:", upstream.stats()["calls"])
    print("  等后台换血结束，刷新中的航班数:", end=" ")
    deadline = time.perf_counter() + 1.0
    while cache.stats()["refreshing"] and time.perf_counter() < deadline:
        time.sleep(0.002)
    print(cache.stats()["refreshing"])
    print("  再查拿到新值 ->", cache.lookup("api.svc.internal"),
          "上游调用数:", upstream.stats()["calls"])

    # 刷失败顶旧值：同一条记录再走一遍半程，这次让上游失败。
    upstream.set_failing("api.svc.internal")
    clock.advance(10.0)  # 新 TTL 又过半
    print("  过半后上游挂了，仍拿旧值 ->", cache.lookup("api.svc.internal"))
    clock.advance(10.0)  # 顶到硬过期
    try:
        cache.lookup("api.svc.internal")
    except UpstreamError as exc:
        print("  硬过期才报错:", exc)

    print("=== TTL 抖动：同 TTL 不同到期时刻 ===")
    rng = random.Random(20260922)
    jittered = ResolverCache(
        FakeUpstream({"n%d.svc.internal" % i: ("10.2.0.%d" % i, 20.0)
                      for i in range(4)}),
        clock=ManualClock(6000.0), jitter=0.5, rng=rng)
    for i in range(4):
        name = "n%d.svc.internal" % i
        jittered.lookup(name)
        entry = jittered._entries[name]
        print("  %s 有效到 6000+%.2fs（基础 TTL 20s，±50%%）"
              % (name, entry.expires_at - 6000.0))


def show_diff():
    print("=== 跟直连上游对拍 ===")
    for seed in (20260921, 1, 7):
        report = run_diff(seed=seed)
        print(" ", report.summary())
        print("  通过:", report.ok())


def main():
    show_hit_and_expiry()
    show_concurrent_same_name()
    show_negative_cache()
    show_single_flight_failure_broadcast()
    show_background_refresh_and_jitter()
    show_diff()


if __name__ == "__main__":
    main()
