"""熔断器现状演示。

第一段：连续失败触发熔断、冷却期内拒绝、冷却结束后恢复放行。
第二段：注释里留了半开探测演示的位子。
"""

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

    # TODO(半开改造): 三态实现后，在这里演示冷却结束进入 half-open：
    # 并发 5 个请求只放行 3 个探测，2 次成功闭合、任一失败立即重开
    # 并按抖动公式重新计时。


if __name__ == "__main__":
    main()
