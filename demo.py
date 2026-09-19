"""熔断器现状演示。

第一段：连续失败触发熔断、冷却期内拒绝、冷却结束后恢复放行。
第二段：半开探测演示（名额、闭合、失败重开与抖动重新计时）。
"""

import threading

from breaker.core import CircuitBreaker

RAND_VALUE = 0.25  # 注入固定随机源，让抖动演示输出可复现


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
    b = CircuitBreaker(threshold=3, cooldown=30.0, clock=clock,
                       rand=lambda: RAND_VALUE)

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

    print("=== 半开探测（名额 3，成功 2 次闭合，失败即重开） ===")
    # 上一段末尾冷却结束，b 已进入 half-open，刚才那次放行用掉了 1 个名额
    b.record_failure()
    jittered = 30.0 * (0.8 + 0.4 * RAND_VALUE)
    print(f"  t={clock.now:.0f}s 探测失败 -> OPEN（已发名额作废）")
    print(f"  本次冷却 = 30*(0.8+0.4*{RAND_VALUE}) = {jittered:.1f}s（抖动重新计时）")

    clock.advance(jittered)
    print(f"  t={clock.now:.1f}s（冷却结束）-> half-open，重发 3 个探测名额")

    start = threading.Event()
    results = []

    def probe():
        start.wait()
        results.append(b.allow_request())

    threads = [threading.Thread(target=probe) for _ in range(5)]
    for t in threads:
        t.start()
    start.set()  # 5 个请求同一时刻竞争探测名额
    for t in threads:
        t.join()
    print(f"  并发 5 个请求 -> 放行 {sum(results)} 个，"
          f"拒绝 {len(results) - sum(results)} 个（名额 3，不超发）")

    b.record_success()
    b.record_success()
    print(f"  2 次探测成功 -> CLOSED，全量放行? {b.allow_request()}")


if __name__ == "__main__":
    main()
