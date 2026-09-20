"""shapeq 演示。

第一段：固定窗口计数——窗口内额度用满就拒，跨窗口重新放行。
第二段：令牌桶整形与多租户公平——突发被桶容量吸收，超出的
请求按速率排队或拒绝，租户之间配额互不挤占。
"""

from shapeq.limiter import FixedWindowLimiter
from shapeq.shaper import TokenBucketShaper


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

    # === 第二段：令牌桶整形 + 多租户公平 ===
    # 每租户桶容量 2（突发）、每秒补 1 个（整形速率），最多等 5 秒。
    shaper = TokenBucketShaper(
        capacity=2, refill_rate=1.0, max_wait=5.0, clock=clock
    )

    print("=== 令牌桶整形（桶容量 2，每秒补 1） ===")
    for i in range(4):
        t = shaper.acquire("noisy")
        note = f"预计 t={t.ready_at:.0f}s 可取" if t.status == "queued" else ""
        print(f"  t={clock.now:.0f}s noisy 第 {i + 1} 次 -> {t.status} {note}")

    # 吵闹租户在排队，安静租户的请求立刻拿到自己的令牌：公平不挤占。
    q = shaper.acquire("quiet")
    print(f"  t={clock.now:.0f}s quiet 请求 -> {q.status}（没被 noisy 挤掉）")

    print("  -- 时钟推进 2s，按补充点放行队列 --")
    clock.advance(2.0)
    for t in shaper.pump():
        print(f"  t={clock.now:.0f}s 放行 {t.tenant} 的排队请求")
    s = shaper.stats()
    print(
        f"  stats: allowed={s['allowed']} rejected={s['rejected']} "
        f"queued={s['queued']} tokens={ {k: round(v, 2) for k, v in s['tokens'].items()} }"
    )

    print("=== 等不起就拒：max_wait=0.5，桶空直接给结果 ===")
    strict = TokenBucketShaper(
        capacity=1, refill_rate=1.0, max_wait=0.5, clock=clock
    )
    strict.acquire("batch")
    t = strict.acquire("batch")       # 预计要等 1s，超过上限
    print(f"  t={clock.now:.0f}s batch 超出的请求 -> {t.status}")
    s = strict.stats()
    print(f"  stats: allowed={s['allowed']} rejected={s['rejected']} queued={s['queued']}")


if __name__ == "__main__":
    main()
