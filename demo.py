"""intervalx 快速演示。

第一段跑改造前的基线能力（两两比较的合并与交集、逐点逐区间的覆盖长度与最大
重叠数、贪心最少覆盖，以及朴素比较次数与访问次数的规模对照）。
第二段预留给改造后的扫描线路径演示，待实现补齐。
"""

from intervalx.interval import IntervalSet


def demo_baseline():
    print("== 基线：两两比较的合并与交集 ==")
    s = IntervalSet([(1, 4), (2, 6), (8, 10), (9, 12), (20, 21)])
    print("合并 =", s.merge())
    print("交集 =", s.intersection())
    print("并集总长度 =", s.union_length())

    print("== 基线：逐点逐区间的覆盖与最大重叠 ==")
    print("点 3 的覆盖数 =", s.coverage_count(3))
    print("点 9 被覆盖下标 =", s.covers_point(9))
    print("最大重叠数 =", s.max_overlap())

    print("== 基线：两两包含与最少覆盖 ==")
    inner = IntervalSet([(1, 10), (2, 5), (3, 4), (20, 25)])
    print("被包含对 =", inner.containment())
    cover = IntervalSet([(1, 4), (2, 8), (6, 12), (9, 15)])
    target = (1, 15)
    pick = cover.cover_with(target)
    print("覆盖", target, "用下标 =", pick)

    print("== 基线：独立慢速做法 ==")
    print("独立合并 =", s.independent_brute_merge())
    print("独立最大重叠 =", s.independent_brute_max_overlap())

    print("== 基线：规模对照 ==")
    for n in (4, 8, 12):
        big = IntervalSet([(i, i + 3) for i in range(n)])
        big.merge()
        print("%d 个区间：两两比较 %d 次，逐点访问 %d 次"
              % (n, big.comparison_count(), big.access_count()))


def demo_optimized():
    # TODO: 第二段演示（实现后补）
    pass


def main():
    demo_baseline()
    demo_optimized()


if __name__ == "__main__":
    main()
