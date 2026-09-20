"""熔断器现状演示。

第一段：连续失败触发熔断、冷却期内拒绝、冷却结束后恢复放行。
第二段：冷却结束进入 half-open，并发探测限 3 个名额、
两次成功闭合；探测失败立即回 open 并按新抖动重新计时。
"""

import threading

from breaker.core import CircuitBreaker


class ManualClock:
    """demo 用的手动时钟，逐段推进时间，不真正 sleep。"""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def main():
    clock = ManualClock()
    b = CircuitBreaker(threshold=3, cooldown=30.0, clock=clock)

    print("=== 熔断器现状（阈值 3，冷却 30s） ===")
    for i in range(3):
        b.record_failure()
        state = "OPEN" if b.is_open() else "closed"
        print(f"  t={clock.now:.0f}s 失败 #{i + 1} -> {state}")

    print(f"  t={clock.now:.0f}s 放行请求? {b.allow_request()}（熔断中，拒绝全部）")

    clock.advance(15.0)
    print(f"  t={clock.now:.0f}s（冷却中段）放行请求? {b.allow_request()}")

    clock.advance(45.0)
    print(f"  t={clock.now:.0f}s（冷却结束）放行请求? {b.allow_request()}")

    def concurrent_probes(breaker, count):
        """count 个请求同时撞熔断器，用 Event 同发令，返回放行结果。"""
        gate = threading.Event()
        results = []
        results_lock = threading.Lock()

        def probe():
            gate.wait()
            allowed = breaker.allow_request()
            with results_lock:
                results.append(allowed)

        threads = [threading.Thread(target=probe) for _ in range(count)]
        for thread in threads:
            thread.start()
        gate.set()
        for thread in threads:
            thread.join()
        return results

    print()
    print("=== 三态改造：half-open 探测（阈值 1，冷却 30s，r 固定 0.0） ===")
    hclock = ManualClock()
    hb = CircuitBreaker(threshold=1, cooldown=30.0, clock=hclock,
                        rng=lambda: 0.0)
    hb.record_failure()
    print(f"  t={hclock.now:.0f}s 失败 -> {hb.state()}（冷却 30*(0.8+0.4*0)=24s）")

    results = concurrent_probes(hb, 5)
    print(f"  t={hclock.now:.0f}s 冷却中并发 5 个 -> 放行 {sum(results)} 个（全拒）")

    hclock.advance(24.0)
    print(f"  t={hclock.now:.0f}s 冷却满 -> {hb.state()}（名额 3 个）")
    results = concurrent_probes(hb, 5)
    print(f"  t={hclock.now:.0f}s 并发 5 个探测 -> 放行 {sum(results)} 个，拒绝 2 个")

    hb.record_success()
    print(f"  t={hclock.now:.0f}s 探测成功 #1 -> {hb.state()}（累计 1/2）")
    hb.record_success()
    print(f"  t={hclock.now:.0f}s 探测成功 #2 -> {hb.state()}，计数清零，恢复全量放行")

    print()
    print("=== 探测失败：立即回 open，名额作废，按新抖动重新计时 ===")
    fclock = ManualClock()
    rng_values = iter([0.0, 0.5])
    fb = CircuitBreaker(threshold=1, cooldown=30.0, clock=fclock,
                        rng=lambda: next(rng_values))
    fb.record_failure()
    fclock.advance(24.0)
    print(f"  t={fclock.now:.0f}s -> {fb.state()}，发 3 个探测名额")
    fb.allow_request()
    fb.allow_request()
    fb.record_failure()
    print(f"  t={fclock.now:.0f}s 一个探测失败 -> {fb.state()}，剩余名额作废，"
          "本次冷却 30*(0.8+0.4*0.5)=30s")
    fclock.advance(29.999)
    print(f"  t={fclock.now:.0f}s 新冷却未满，放行? {fb.allow_request()}")
    fclock.advance(0.002)
    print(f"  t={fclock.now:.0f}s 新冷却满 -> {fb.state()}，3 个新名额可领")


if __name__ == "__main__":
    main()
