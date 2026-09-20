"""shapeq 演示。

第一段：固定窗口计数——窗口内额度用满就拒，跨窗口重新放行。
第二段：令牌桶整形——突发被桶容量吸收，超额请求排队等补充。
第三段：多租户公平——某租户打满自己那份后排队，其他租户照常拿；
并演示等待上限超时与"超额即拒"两种策略。
"""

from shapeq.limiter import FixedWindowLimiter
from shapeq.shaper import Request, TokenBucketShaper


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
    lim = FixedWindowLimiter(limit=3, window=10.0, clock=clock)

    print("=== 固定窗口计数（每窗口 3 次） ===")
    for i in range(4):
        ok = lim.allow("tenant-a")
        print(f"  t={clock.now:.0f}s 第 {i + 1} 次 -> {'放行' if ok else '拒绝'}")

    clock.advance(10.0)
    print(f"  t={clock.now:.0f}s（新窗口）-> {'放行' if lim.allow('tenant-a') else '拒绝'}")

    s = lim.stats()
    print(f"  stats: allowed={s['allowed']} rejected={s['rejected']} keys={s['keys']}")

    print()
    print("=== 令牌桶整形（共享 1 令牌/秒，桶容量 3，可排队 10s） ===")
    clock2 = ManualClock()
    shaper = TokenBucketShaper(
        shared_rate=1.0, shared_burst=3,
        tenant_rate=1.0, tenant_burst=3,
        timeout=10.0, clock=clock2,
    )
    results = [shaper.acquire("a") for _ in range(4)]
    print(f"  t={clock2.now:.0f}s 连发 4 个 -> "
          f"{[r.status for r in results]}（前 3 个突发被吸收，第 4 个排队）")
    clock2.advance(1.0)
    shaper.pump()
    print(f"  t={clock2.now:.0f}s 补出 1 枚 -> 排队者 {results[3].status}，"
          f"等待 {results[3].waited:.0f}s")

    print()
    print("=== 多租户公平（共享 2 令牌/秒，每租户突发上限 2） ===")
    clock3 = ManualClock()
    fair = TokenBucketShaper(
        shared_rate=2.0, shared_burst=6,
        tenant_rate=2.0, tenant_burst=2,
        timeout=100.0, clock=clock3,
    )
    a_reqs = [fair.acquire("tenant-a") for _ in range(6)]  # A 半夜跑批
    b_reqs = [fair.acquire("tenant-b") for _ in range(3)]
    print(f"  t={clock3.now:.0f}s A 连发 6 个、B 连发 3 个")
    print(f"    A: {[r.status for r in a_reqs]}")
    print(f"    B: {[r.status for r in b_reqs]}（B 的即时份额不受影响）")
    clock3.advance(1.0)
    fair.pump()
    print(f"  t={clock3.now:.0f}s 补充后 round-robin 结算：")
    print(f"    A 已放行 {sum(r.granted for r in a_reqs)}/6，"
          f"B 已放行 {sum(r.granted for r in b_reqs)}/3（交替放行，B 先走完）")

    print()
    print("=== 等待上限与超额即拒 ===")
    clock4 = ManualClock()
    bounded = TokenBucketShaper(
        shared_rate=0.1, shared_burst=1,
        tenant_rate=0.1, tenant_burst=1,
        timeout=1.0, clock=clock4,
    )
    bounded.acquire("tenant-a")
    waiting = bounded.acquire("tenant-a")
    clock4.advance(1.5)
    bounded.pump()
    print(f"  排队策略：等过上限 -> {waiting.status}（reason={waiting.reason}）")

    strict = TokenBucketShaper(
        shared_rate=1.0, shared_burst=1,
        tenant_rate=1.0, tenant_burst=1,
        timeout=0.0,
    )
    strict.acquire("tenant-a")
    dropped = strict.acquire("tenant-a")
    print(f"  即拒策略：桶空 -> {dropped.status}（reason={dropped.reason}）")

    s2 = bounded.stats()
    print(f"  stats(等待上限): 剩余令牌={s2['tokens']} "
          f"granted={s2['granted']} rejected={s2['rejected']} "
          f"timed_out={s2['timed_out']} 队列长={s2['waiting']}")


if __name__ == "__main__":
    main()
