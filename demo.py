"""熔断器演示。

第一段：连续失败触发熔断、冷却期内拒绝、冷却结束进入 half-open。
第二段：半开探测演示——并发名额不超发、两次成功闭合、任一失败
立即重开并按抖动公式重新计时。全程手动时钟，不真正 sleep。
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


class ScriptedRandom:
    """按脚本返回 r 值，让抖动结果可演示。"""

    def __init__(self, values):
        self._values = list(values)
        self._index = 0

    def __call__(self):
        value = self._values[self._index % len(self._values)]
        self._index += 1
        return value


def run_concurrent(breaker, count):
    """count 个线程经同一个 Event 同时发起 allow_request。"""
    results = []
    go = threading.Event()

    def worker():
        go.wait()
        results.append(breaker.allow_request())

    threads = [threading.Thread(target=worker) for _ in range(count)]
    for thread in threads:
        thread.start()
    go.set()
    for thread in threads:
        thread.join()
    return results


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
    print(f"  t={clock.now:.0f}s（冷却结束）状态={b.state}，只放行探测，不再全量放行")

    print()
    print("=== 半开探测演示（阈值 3，冷却 30s，抖动脚本 r=[0.5, 0.0]） ===")

    c2 = ManualClock()
    b2 = CircuitBreaker(
        threshold=3, cooldown=30.0, clock=c2,
        random=ScriptedRandom([0.5, 0.0]),
    )
    for _ in range(3):
        b2.record_failure()
    print(f"  t={c2.now:.0f}s 连续失败 3 次 -> {b2.state}（首次冷却固定 30s）")

    c2.advance(30.0)
    print(f"  t={c2.now:.0f}s 冷却结束 -> {b2.state}，名额 3 个")

    results = run_concurrent(b2, 5)
    print(f"  并发 5 个请求：放行 {sum(results)} 个探测，拒绝 {results.count(False)} 个（不超发）")

    b2.record_success()
    b2.record_success()
    print(f"  探测累计 2 次成功 -> {b2.state}（计数清零，全量恢复）")
    print(f"  闭合后并发 5 个请求：放行 {sum(run_concurrent(b2, 5))} 个")

    for _ in range(3):
        b2.record_failure()
    print(f"  下游再次故障，连续失败 3 次 -> {b2.state}")
    c2.advance(30.0)
    print(f"  t={c2.now:.0f}s 冷却结束 -> {b2.state}")

    b2.allow_request()
    b2.record_failure()
    print(f"  探测失败 -> {b2.state}，按 r=0.5 重新计时：30*(0.8+0.4*0.5)=30s")
    c2.advance(29.0)
    print(f"  t={c2.now:.0f}s 差 1s 到期，放行? {b2.allow_request()}")
    c2.advance(1.0)
    print(f"  t={c2.now:.0f}s 到期 -> {b2.state}，已发名额作废后重新放出 3 个")
    results = run_concurrent(b2, 5)
    print(f"  新一轮并发 5 个请求：放行 {sum(results)} 个探测，拒绝 {results.count(False)} 个")

    b2.allow_request()
    b2.record_failure()
    print(f"  探测再失败 -> {b2.state}，按 r=0.0 重新计时：30*0.8=24s（抖动下限）")
    c2.advance(24.0)
    print(f"  t={c2.now:.0f}s 到期 -> {b2.state}")


if __name__ == "__main__":
    main()
