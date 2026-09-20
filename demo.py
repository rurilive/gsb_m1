"""tracesamp 演示：自适应模式的四个关键场景。

假时钟驱动，几秒钟跑完（场景四用真实时钟压并发）。每个场景把
"期望"和"实际"并排打出来，可以直接对着看：平稳流量贴目标、
同一 trace 结论一致、峰值过后沉得回来、并发吞吐留有余量。
"""

import threading
import time

from tracesamp import ManualClock, TraceSampler


def pump(sampler, clock, spans_per_second, seconds, tag, spans_per_trace=3):
    """灌 seconds 秒的流量，返回 (每秒采样条数, 采样总条数)。"""
    total = int(spans_per_second * seconds)
    step = 1.0 / spans_per_second
    per_second = []
    kept = 0
    total_kept = 0
    for index in range(total):
        if sampler.should_sample("%s-%d" % (tag, index // spans_per_trace)):
            kept += 1
            total_kept += 1
        clock.advance(step)
        if (index + 1) % int(spans_per_second) == 0:
            per_second.append(kept)
            kept = 0
    return per_second, total_kept


def scenario_steady_traffic():
    print("=== 场景一：平稳流量下的自适应（目标 150 条/秒，流量 1200 span/秒）===")
    clock = ManualClock()
    sampler = TraceSampler(mode="adaptive", target_per_sec=150.0, clock=clock)
    per_second, _ = pump(sampler, clock, 1200, 8, "steady")
    print("  每秒采样条数：", per_second)
    print("  当前采样率  ：", round(sampler.rate(), 4))
    print("  期望：每一秒都贴着 150 上下小幅走，采样率稳住不再乱动")


def scenario_trace_consistency():
    print("=== 场景二：同一个 trace 的 span 决策 ===")
    clock = ManualClock()
    sampler = TraceSampler(mode="adaptive", target_per_sec=150.0, clock=clock)
    pump(sampler, clock, 3000, 2, "warmup")

    arrived = []
    for _ in range(12):
        arrived.append(sampler.should_sample("trace-checkout"))
        clock.advance(0.05)
    print("  trace-checkout 的 12 个 span 隔 50 毫秒陆续到达：", arrived)

    kept_per_round = []
    guard = threading.Lock()

    def round_worker(pool, barrier):
        barrier.wait()
        local = [sampler.should_sample("trace-pay") for _ in range(6)]
        with guard:
            pool.extend(local)

    for round_index in range(8):
        pool = []
        barrier = threading.Barrier(8)
        threads = [threading.Thread(target=round_worker, args=(pool, barrier))
                   for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        kept_per_round.append(pool.count(True))
        pump(sampler, clock, 3000, 0.12, "filler-%d" % round_index)
    print("  8 路并发同时取同一条 trace-pay 的 6 个 span，重复八轮，"
          "每轮 48 条里采到的条数：", kept_per_round)
    print("  期望：同一条 trace 要么全采要么全丢，每一轮只该是 0 或 48")


def scenario_burst_then_calm():
    print("=== 场景三：峰值过后流量回落（目标 200 条/秒）===")
    clock = ManualClock()
    sampler = TraceSampler(mode="adaptive", target_per_sec=200.0, clock=clock)
    burst, _ = pump(sampler, clock, 4000, 3, "burst")
    rate_after_burst = sampler.rate()
    calm, _ = pump(sampler, clock, 300, 6, "calm")
    print("  峰值 4000 span/秒的 3 秒：", burst)
    print("  峰值刚过时的采样率  ：", round(rate_after_burst, 4))
    print("  回落到 300 span/秒的 6 秒：", calm)
    print("  回落结束时的采样率  ：", round(sampler.rate(), 4))
    print("  期望：回落后每一秒都贴着 200 上下，采样率别再钉在最高档")


def scenario_concurrent_throughput():
    print("=== 场景四：8 路并发灌流量（自适应模式，真实时钟）===")
    sampler = TraceSampler(mode="adaptive", target_per_sec=1000000.0)
    workers = 8
    per_worker = 10000
    barrier = threading.Barrier(workers)

    def worker(worker_id):
        barrier.wait()
        for index in range(per_worker):
            sampler.should_sample("w%d-%d" % (worker_id, index // 3))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(workers)]
    start = time.perf_counter()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    elapsed = time.perf_counter() - start
    total = workers * per_worker
    print("  %d 条 span，8 路并发，耗时 %.3f 秒，约 %.0f 条/秒"
          % (total, elapsed, total / elapsed))
    print("  期望：改前改后拿同一个脚本对着跑，吞吐别比初始版本差一截")


def main():
    scenario_steady_traffic()
    print()
    scenario_trace_consistency()
    print()
    scenario_burst_then_calm()
    print()
    scenario_concurrent_throughput()


if __name__ == "__main__":
    main()
