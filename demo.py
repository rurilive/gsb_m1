"""EventCounter 现状演示。

第一段：按事件时间累计计数，乱序到达不影响总和。
第二段：预留的滑动窗口与多窗口演示位子（见文末注释）。
"""

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

    # TODO(滑动窗口): 窗口查询、乱序修正与多窗口并行落地后，在这里加一段演示：
    # 推进假时钟，展示最近 N 秒的窗口和随事件滑出而下降；
    # 补一条落在窗口内的迟到事件看它被计入，再补一条早于左边界的看它被丢弃或记迟到；
    # 最后同时挂两个不同长度的窗口，展示短窗口先淘汰、长窗口仍保留。


if __name__ == "__main__":
    main()
