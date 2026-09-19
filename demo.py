"""直方图演示。

第一段：记录一批样本，输出 count 与常用分位数。
第二段：注入时钟演示滑动窗口推进。
"""

from metricbox.histogram import Histogram

LATENCIES = [12, 18, 22, 25, 30, 31, 34, 40, 88, 120, 17, 19, 23, 27, 95]


def main():
    h = Histogram()
    for v in LATENCIES:
        h.observe(v)

    print("=== 直方图现状（全量样本） ===")
    print(f"  count = {h.count()}")
    ps = h.percentiles(0.5, 0.9, 0.99)
    for p in (0.5, 0.9, 0.99):
        print(f"  p{int(p * 100):02d} = {ps[p]}")

    print()
    print("=== 滑动窗口（window_seconds=10，注入时钟） ===")

    class DemoClock:
        def __init__(self):
            self.now = 0.0

        def __call__(self):
            return self.now

    clock = DemoClock()
    wh = Histogram(window_seconds=10, clock=clock)
    for v in (100, 101, 102):
        wh.observe(v)
    print(f"  t={clock.now:g}: count = {wh.count()}（窗口内 3 个旧样本）")

    clock.now = 6
    wh.observe(20)
    print(f"  t={clock.now:g}: count = {wh.count()}（新样本进入窗口）")

    clock.now = 10
    print(f"  t={clock.now:g}: observe 挤出 {wh.observe(21)} 个（恰满窗口仍算窗口内）")
    print(f"           count = {wh.count()}")

    clock.now = 11
    print(f"  t={clock.now:g}: observe 挤出 {wh.observe(22)} 个旧样本，count = {wh.count()}")

    clock.now = 20
    print(f"  t={clock.now:g}: 读取只算窗口内 count = {wh.count()}，compact 清理 {wh.compact()} 个")

    wh.observe(15)
    wh.observe(45)
    print(f"  snapshot([20, 40]) = {wh.snapshot([20, 40])}（值等于边界归右桶）")


if __name__ == "__main__":
    main()
