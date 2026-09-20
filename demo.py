"""EventCounter 现状演示。

第一段：按事件时间累计计数，乱序到达不影响总和。
第二段：滑动窗口与多窗口并行演示。
"""

from winagg.sliding import WindowSet
from winagg.window import EventCounter


class FakeClock:
    """可手动推进的假时钟。"""

    def __init__(self, start=1000.0):
        self.now = start

    def __call__(self):
        return self.now

    def tick(self, dt):
        self.now += dt


def main():
    clock = FakeClock()
    counter = EventCounter(clock=clock)

    print("=== 按事件时间累计计数 ===")
    for ts, v in [(100.0, 2), (103.0, 5), (101.0, 1)]:
        clock.tick(1.0)
        total = counter.add(ts, v)
        print(f"  add(ts={ts}, v={v}) -> total={total}")
    print(f"  count={counter.count()} span={counter.span()} "
          f"last_arrival={counter.last_arrival()}")

    print("=== 滑动窗口与多窗口并行 ===")
    windows = WindowSet(clock=clock)
    short = windows.add_window(10.0, 5.0)   # 最近 10 秒，5 秒一桶
    long_ = windows.add_window(30.0, 5.0)   # 最近 30 秒，5 秒一桶

    for ts, v in [(100.0, 2), (103.0, 3), (108.0, 1), (120.0, 4)]:
        clock.tick(1.0)  # 推进到达时钟，窗口推进只看事件时间
        windows.add(ts, v)
        print(f"  add(ts={ts}, v={v}) -> "
              f"short(10s)={short.sum()} long(30s)={long_.sum()}")

    print("  -- 乱序：落在窗口内的迟到事件仍计入 --")
    print(f"  add(ts=112.0, v=5) -> {windows.add(112.0, 5)} "
          f"short={short.sum()} long={long_.sum()}")

    print("  -- 早于左边界：按策略丢弃并记迟到数 --")
    print(f"  add(ts=105.0, v=7) -> {windows.add(105.0, 7)} "
          f"late_count={short.late_count()}/{long_.late_count()}")

    print("  -- 窗口滑出：短窗口先淘汰，聚合成产出 --")
    windows.add(135.0, 1)
    print(f"  add(ts=135.0, v=1) -> short={short.sum()} long={long_.sum()}")
    print(f"  short.closed()={short.closed()}")
    print(f"  short.merge_closed()={short.merge_closed()}")
    print(f"  long.closed()={long_.closed()}  # 长窗口淘汰得更晚")


if __name__ == "__main__":
    main()
