"""subfam 快速演示。

第一段跑改造前的基线能力（朴素最大子段和、长度上界、和最接近上界、极值对照、最大
子段积）。
第二段预留给改造后的单调队列与分治高效路径演示，待实现补齐。
"""

from subfam.stats import SubarrayStats


def demo_baseline():
    print("== 基线：朴素枚举路径 ==")
    k = SubarrayStats()

    seq = [-2, 1, -3, 4, -1, 2, 1, -5, 4]
    r = k.best_sum(seq)
    print("最大子段和 =", r.value, " 区间 =", (r.left, r.right), " 扫描次数 =", r.scan)

    b = k.bounded_sum(seq, 3)
    print("长度不超三的最大子段和 =", b.value, " 区间 =", (b.left, b.right))

    a = k.at_most_sum(seq, 6)
    print("和不超过六的最大子段和 =", a.value, " 区间 =", (a.left, a.right))

    e = k.range_extremes(seq)
    print("全序列极值 =", (e.min_value, e.max_value), " 扫描次数 =", e.scan)

    p = k.best_product([2, 3, -2, 4])
    print("最大子段积 =", p.value, " 含零 =", p.has_zero, " 区间 =", (p.left, p.right))

    print("空序列最大子段和 =", k.best_sum([]).value)


def demo_optimized():
    # TODO: 第二段演示（实现后补）
    pass


def main():
    demo_baseline()
    demo_optimized()


if __name__ == "__main__":
    main()
