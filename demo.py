"""熔断器现状演示。

第一段：连续失败触发熔断、冷却期内拒绝、冷却结束后恢复放行。
第二段：冷却结束进入 half-open，并发探测、两次成功闭合、失败重开加抖动。
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

    print()
    print("=== 半开探测（名额 3，累计 2 次成功闭合） ===")
    clock2 = ManualClock()
    b2 = CircuitBreaker(threshold=3, cooldown=30.0, clock=clock2, r=lambda: 0.5)
    for _ in range(3):
        b2.record_failure()
    print(f"  t={clock2.now:.0f}s 连续失败 3 次 -> OPEN")

    clock2.advance(30.0)
    start = threading.Event()
    granted = []
    granted_lock = threading.Lock()

    def probe():
        start.wait()
        if b2.allow_request():
            with granted_lock:
                granted.append(1)

    threads = [threading.Thread(target=probe) for _ in range(5)]
    for t in threads:
        t.start()
    start.set()
    for t in threads:
        t.join()
    print(f"  t={clock2.now:.0f}s 冷却结束，并发 5 个请求 -> 只放行 {len(granted)} 个探测")

    b2.record_success()
    print("  探测成功 1 次 -> 仍处 half-open，未闭合")
    b2.record_success()
    print(f"  探测成功第 2 次 -> closed，全量放行? {b2.allow_request()}")

    for _ in range(3):
        b2.record_failure()
    print("  再次连续失败 3 次 -> OPEN")
    clock2.advance(30.0)
    print(f"  t={clock2.now:.0f}s 冷却结束，放行探测? {b2.allow_request()}")
    b2.record_failure()
    print(f"  探测失败 -> 立即回 OPEN? {b2.is_open()}，按 cooldown*(0.8+0.4*r) 抖动重新计时")


if __name__ == "__main__":
    main()
