"""直方图现状演示。

第一段：记录一批样本，输出 count 与常用分位数。
第二段：注释里留了滑动窗口演示的位子。
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

    # TODO(窗口改造): 滑动窗口实现后，在这里演示窗口推进：
    # 用注入时钟模拟时间流逝，展示旧样本被挤出窗口、
    # count 与分位数随之变化、observe 的返回值、snapshot 分桶。


if __name__ == "__main__":
    main()
