"""直方图现状演示。

第一段：记录一批样本，输出 count 与常用分位数。
第二段：注释里留了滑动窗口演示的位子。
"""

from metricbox.histogram import Histogram

LATENCIES = [12, 18, 22, 25, 30, 31, 34, 40, 88, 120, 17, 19, 23, 27, 95]


class FakeClock:
    """可手动推进的时钟，用于演示窗口滑动。"""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


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
    print("=== 滑动窗口（window_seconds=60，注入时钟） ===")
    clock = FakeClock()
    w = Histogram(window_seconds=60, clock=clock)
    for v in (100, 110, 120):  # t=0 的旧高延迟样本
        w.observe(v)
    clock.advance(30)
    for v in (20, 25, 30):  # t=30 的新样本
        w.observe(v)
    print(f"  t=30  count = {w.count()}  p99 = {w.percentiles(0.99)[0.99]}")

    clock.advance(45)  # t=75：旧样本已 75 秒，出窗
    evicted = w.observe(35)
    print(f"  t=75  observe 挤出 {evicted} 个旧样本")
    print(f"  t=75  count = {w.count()}  p99 = {w.percentiles(0.99)[0.99]}")
    print(f"  t=75  snapshot([50, 100]) = {w.snapshot([50, 100])}")
    clock.advance(61)  # 全部样本过期
    print(f"  t=136 compact() 清理 {w.compact()} 个样本，count = {w.count()}")


if __name__ == "__main__":
    main()
