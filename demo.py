"""resolvcache 行为演示。

第一段：命中、过期与上游失败。
第二段：多个线程同时查同一个域名，单飞只放一路回源。
第三段：本轮新行为——负缓存、后台预刷新与失败顶旧值。
第四段：跟直连上游对拍，看随机序列下的返回与上游调用数。
"""

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


def _wait_for(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and not predicate():
        time.sleep(0.001)
    return predicate()


def show_negative_cache():
    print("=== 负缓存：上游抖动不再打穿 ===")
    upstream = FakeUpstream({"db.svc.internal": ("10.0.0.40", 30.0)})
    clock = ManualClock(3000.0)
    cache = ResolverCache(upstream, clock=clock, negative_ttl=5.0)
    upstream.set_failing("db.svc.internal")
    for _ in range(5):
        try:
            cache.lookup("db.svc.internal")
        except UpstreamError:
            pass
    print("  连续查 5 次失败域名，上游调用数:", upstream.stats()["calls"])
    clock.advance(6.0)
    try:
        cache.lookup("db.svc.internal")
    except UpstreamError:
        pass
    print("  负缓存 5 秒过期后再查，上游调用数:", upstream.stats()["calls"])


def show_refresh_and_stale():
    print("=== 后台预刷新 / 失败拿旧值顶到硬过期 ===")
    upstream = FakeUpstream({"api.svc.internal": ("10.0.0.10", 20.0)})
    clock = ManualClock(4000.0)
    cache = ResolverCache(upstream, clock=clock)
    print("  首次 lookup ->", cache.lookup("api.svc.internal"))
    upstream.set_record("api.svc.internal", "10.0.0.11", 20.0)
    clock.advance(11.0)  # 有效期 20 秒，已过半
    print("  过半后命中先返回旧值 ->", cache.lookup("api.svc.internal"))
    _wait_for(lambda: cache.lookup("api.svc.internal") == "10.0.0.11")
    print("  后台刷新落地后再查 ->", cache.lookup("api.svc.internal"))
    upstream.set_failing("api.svc.internal")
    clock.advance(11.0)  # 又过半，这次后台刷新会失败
    print("  上游挂了，过半后仍返回旧值 ->", cache.lookup("api.svc.internal"))
    _wait_for(lambda: cache.stats()["errors"] == 1)
    clock.advance(5.0)
    print("  硬过期前一直是旧值 ->", cache.lookup("api.svc.internal"))
    clock.advance(6.0)  # 过了硬过期，按未命中重新回源
    try:
        cache.lookup("api.svc.internal")
    except UpstreamError as exc:
        print("  硬过期后回源仍失败:", exc)


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
    show_refresh_and_stale()
    show_diff()


if __name__ == "__main__":
    main()
