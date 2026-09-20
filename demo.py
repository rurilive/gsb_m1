"""SnapshotStore 现状演示。

第一段：连拍三张，回到中间某一时刻取当时的状态。
第二段：预留的保留策略演示位子（见文末注释）。
"""

from snapkeep.snapshots import RetentionPolicy, SnapshotStore


class FakeClock:
    """可手动推进的假时钟，方便把时间轴演给用户看。"""

    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


def main():
    clock = FakeClock()
    store = SnapshotStore(clock=clock)

    print("=== 连拍与按时刻读取 ===")
    for v in ("v1", "v2", "v3"):
        clock.advance(60)
        ts = store.take("dev-7", v)
        print(f"  take(dev-7, {v!r}) @ {ts:.0f}")
    print("  list(dev-7):", [f"{t:.0f}" for t in store.list("dev-7")])
    for t in (1000.0, 1060.0, 1090.0, 1180.0):
        print(f"  get(dev-7, {t:.0f}) -> {store.get('dev-7', t)!r}")

    print("=== 保留策略与回收 ===")
    # 最近 1 小时一条不动；1~3 小时每小时留最后一张；更早每天留最后一张；
    # 每对象最多 50 条兜底。gc_interval 控制两次回收的最小间隔。
    policy = RetentionPolicy(recent_window=3600, hourly_window=3 * 3600,
                             max_per_obj=50)
    store = SnapshotStore(clock=clock, retention=policy, gc_interval=60)
    clock.t = 0.0
    # 模拟密集写入：每 10 分钟一张，连拍 100 小时
    pinned_ts = None
    for i in range(600):
        clock.advance(600)
        ts = store.take("dev-9", f"s{i}")
        if i == 7:
            pinned_ts = ts  # 事故复盘要盯的一张，当场按住
            store.pin("dev-9", pinned_ts)
    released = store.collect_now()  # 立即补一轮回收（跳过节流）
    kept = store.list("dev-9")
    print(f"  拍了 600 张，回收后剩 {len(kept)} 张，本轮释放 {released} 张")
    print("  最近 5 张:", [f"{t:.0f}" for t in kept[-5:]])
    print("  最早 5 张:", [f"{t:.0f}" for t in kept[:5]])
    print(f"  pin 住的 {pinned_ts:.0f} 还在: {pinned_ts in kept}")
    stats = store.gc_stats()
    print(f"  回收统计: 跑了 {stats['runs']} 轮，"
          f"最近一次 @ {stats['last_run']:.0f}，"
          f"累计释放 {stats['total_released']} 张")


if __name__ == "__main__":
    main()
