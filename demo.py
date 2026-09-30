"""circlp 快速演示。

第一段跑改造前的基线能力（枚举断点拆环的环形不相邻最大和、环形最大子段和、
最优划分、最优选取方案、环相邻差最大和、最小不相邻删除代价，以及两条独立慢速
做法与朴素路径的对账和规模对照）。
第二段预留给改造后的线性路径演示，待实现补齐。
"""

from circlp.circular import CircularOpt


def demo_baseline():
    print("== 基线：环形不相邻最大和 ==")
    c = CircularOpt([2, 3, 2])
    print("圆环 2 3 2 的最大不相邻和 =", c.brute_max_sum(),
          " 断点试探次数 =", c.break_trial_count)
    print("最优选取下标 =", CircularOpt([2, 3, 2]).brute_plan())

    print("== 基线：环形最大子段和 ==")
    c = CircularOpt([5, -3, 5])
    print("圆环 5 -3 5 的最大子段和 =", c.brute_max_segment(),
          " 断点试探次数 =", c.break_trial_count)

    print("== 基线：最优划分 ==")
    print("1 2 3 4 划成两段的最大段和最小值 =",
          CircularOpt([1, 2, 3, 4]).brute_best_partition(2))

    print("== 基线：两项独立能力 ==")
    print("环相邻差最大和（1 5 2）= ", CircularOpt([1, 5, 2]).brute_diff_sum())
    print("最小不相邻删除代价（5 1 4 2 3 删两个）= ",
          CircularOpt([5, 1, 4, 2, 3]).brute_min_delete(2))

    print("== 基线：独立慢速做法对账 ==")
    values = [7, -1, 4, -2, 6, -3, 2]
    a = CircularOpt(values)
    print("两侧线性递推 =", a.independent_split(), " 朴素断点枚举 =", a.brute_max_sum())
    b = CircularOpt(values)
    print("总和减小段 =", b.independent_minus(), " 朴素断点枚举 =", b.brute_max_segment())

    print("== 基线：规模对照 ==")
    for n in range(4, 11):
        values = [((i * 7) % 11) - 5 for i in range(n)]
        naive = CircularOpt(values)
        naive.brute_max_sum()
        fast = CircularOpt(values)
        fast.independent_split()
        print("%d 个元素：朴素断点试探 %d 次，两侧线性递推 %d 次"
              % (n, naive.break_trial_count, fast.linear_step_count))


def demo_optimized():
    # TODO: 第二段演示（实现后补）
    pass


def main():
    demo_baseline()
    demo_optimized()


if __name__ == "__main__":
    main()
