"""resolvcache 现状演示。

第一段：命中、过期与上游失败。
第二段：多个线程同时查同一个域名，数一数上游被打了几次。
第三段：预留的新行为演示位子（见文末注释）。
第四段：跟直连上游对拍，看随机序列下的返回与上游调用数。
"""

import threading

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


# TODO(本轮改造): 新行为的演示位子留在这儿，加在下面这段之前，
# 输出要能一眼看出这轮改了什么。


def show_diff():
    print("=== 跟直连上游对拍 ===")
    for seed in (20260921, 1, 7):
        report = run_diff(seed=seed)
        print(" ", report.summary())
        print("  通过:", report.ok())


def main():
    show_hit_and_expiry()
    show_concurrent_same_name()
    show_diff()


if __name__ == "__main__":
    main()
