"""shapeq 现状演示。

第一段：固定窗口计数——窗口内额度用满就拒，跨窗口重新放行。
第二段：注释里留了令牌桶整形与多租户公平的演示位子。
"""

from shapeq.limiter import FixedWindowLimiter


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

    # TODO(整形与公平改造): 令牌桶与多租户公平实现后，在这里加一段演示：
    # 注入假时钟，展示按速率补充令牌、突发被桶容量吸收；
    # 再让某个租户打满自己的配额，展示它超出的请求进队列或按策略被拒，
    # 同时其他租户仍能拿到令牌；最后打印剩余令牌、被拒次数与队列长度。


if __name__ == "__main__":
    main()
