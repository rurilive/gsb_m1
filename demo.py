"""SnapshotStore 演示。

第一段：连拍三张，回到中间某一时刻取当时的状态。
第二段：跨三天高密度连拍，展示三档保留、条数兜底、
按住事故时刻快照，以及回收统计。
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


def fmt(ts):
    """把假时钟的秒数格式化成「第N天 HH:MM」，纯演示用。"""
    day = int(ts // 86400)
    hour = int(ts % 86400 // 3600)
    minute = int(ts % 3600 // 60)
    return f"D{day} {hour:02d}:{minute:02d}"


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

    print()
    print("=== 保留策略：三档抽稀 + 条数兜底 + 按住 ===")
    origin = 20 * 86400  # 对齐整天，桶边界干净
    clock.t = origin
    policy = RetentionPolicy(
        recent_seconds=30 * 60,     # 最近 30 分钟：一条不动
        hourly_seconds=6 * 3600,    # 30 分钟到 6 小时：每小时留最后一张
        max_snapshots=30,           # 每对象最多 30 条非按住快照
    )
    gc_store = SnapshotStore(
        clock=clock, retention=policy, gc_interval=100 * 86400
    )

    total = 0
    incident_ts = None
    for day in range(3):
        # 每 20 分钟拍一张，全天 72 张，三天共 216 张。
        for minute in range(0, 24 * 60, 20):
            clock.t = origin + day * 86400 + minute * 60
            label = f"d{day}-{minute // 60:02d}:{minute % 60:02d}"
            gc_store.take("dev-7", label)
            total += 1
            if day == 0 and minute == 2 * 60:
                incident_ts = clock.t  # 事故复盘要盯住的时刻

    print(f"  连拍 {total} 张（3 天 x 每 20 分钟）")
    print(f"  回收前库里 {len(gc_store.list('dev-7'))} 张")
    gc_store.gc()
    print(f"  未 pin 回收一轮后剩余 {len(gc_store.list('dev-7'))} 张；"
          f"事故快照还在吗："
          f"{incident_ts in gc_store.list('dev-7')}")

    # 重新来一遍：这次在回收前把事故时刻按住。
    clock.t = origin
    gc_store = SnapshotStore(
        clock=clock, retention=policy, gc_interval=100 * 86400
    )
    for day in range(3):
        for minute in range(0, 24 * 60, 20):
            clock.t = origin + day * 86400 + minute * 60
            gc_store.take(
                "dev-7", f"d{day}-{minute // 60:02d}:{minute % 60:02d}"
            )
            if clock.t == incident_ts:
                gc_store.pin("dev-7", incident_ts)

    released = gc_store.gc()
    kept = gc_store.list("dev-7")
    print(f"  pin 住 {fmt(incident_ts)} 后回收，本轮释放 {released} 条，"
          f"剩余 {len(kept)} 张：")
    timeline = " ".join(fmt(t) for t in kept)
    print(f"    {timeline}")
    print(f"  get(dev-7, {fmt(incident_ts)}) -> "
          f"{gc_store.get('dev-7', incident_ts)!r}")
    stats = gc_store.gc_stats()
    print(f"  累计回收 {stats['total_released']} 条 / "
          f"{stats['gc_runs']} 轮；最近一轮释放 "
          f"{stats['last_released']} 条 @ "
          f"{fmt(stats['last_run_at'])}")


if __name__ == "__main__":
    main()
