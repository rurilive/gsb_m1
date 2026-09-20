"""EventCounter 现状演示。

第一段：按事件时间累计计数，乱序到达不影响总和。
第二段：预留的滑动窗口与多窗口演示位子（见文末注释）。
"""

from winagg.sliding import MultiWindow, SlidingWindow
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

    print("=== 滑动窗口：最近 10 秒计数和（按事件时间推进）===")
    win = SlidingWindow(10, clock=clock, late_policy="count")
    for ts, v in [(200.0, 3), (205.0, 4), (207.0, 2)]:
        clock.tick(1.0)
        win.add(ts, v)
        print(f"  add(ts={ts}, v={v}) -> 窗口和={win.sum()} "
              f"(暂存 {win.buffered()} 条, watermark={win.watermark()})")
    win.add(206.0, 5)   # 迟到但落在窗口 [197, 207] 内
    print(f"  迟到 ts=206 在窗口内 -> 窗口和={win.sum()}")
    win.add(190.0, 9)   # 早于左边界 197，记迟到
    print(f"  迟到 ts=190 出界 -> 窗口和={win.sum()} late={win.late()}")
    win.add(215.0, 1)   # watermark 推进，ts<205 的被真淘汰
    print(f"  推进到 ts=215 -> 窗口和={win.sum()} (暂存 {win.buffered()} 条)")

    print("=== 窗口关闭产出与相邻合并 ===")
    w2 = SlidingWindow(10, clock=clock)
    for ts, v in [(201.0, 2), (205.0, 3), (212.0, 4), (215.0, 1), (223.0, 1)]:
        w2.add(ts, v)
    ems = w2.drain_emissions()
    for em in ems:
        print(f"  产出 [{em.start}, {em.end}) total={em.total} count={em.count}")
    merged = w2.merge(ems[0], ems[1])
    print(f"  合并 [{merged.start}, {merged.end}) total={merged.total} "
          f"count={merged.count}")

    print("=== 多窗口并行：5s 与 15s 各自淘汰 ===")
    mw = MultiWindow([5, 15], clock=clock)
    for ts, v in [(300.0, 1), (304.0, 2), (309.0, 4)]:
        mw.add(ts, v)
    print(f"  5s 窗口和={mw.sum(5)} (暂存 {mw.window(5).buffered()} 条), "
          f"15s 窗口和={mw.sum(15)} (暂存 {mw.window(15).buffered()} 条)")


if __name__ == "__main__":
    main()
