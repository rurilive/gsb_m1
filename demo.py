"""SnapshotStore 现状演示。

第一段：连拍三张，回到中间某一时刻取当时的状态。
第二段：预留的保留策略演示位子（见文末注释）。
"""

from snapkeep.snapshots import SnapshotStore


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

    # TODO(保留策略): 实现回收后在这里补一段演示：
    # 设保留窗口与每对象条数上限、跨小时/跨天连拍后展示抽稀结果，
    # pin 住一条再回收证明它没被删，并打印释放条数与最近一次回收时刻。


if __name__ == "__main__":
    main()
