"""binanswer 快速演示。

第一段跑改造前的基线能力（逐个试答案的最小最大段和、最大最小段和、
最小整数可行值、序列最小最大差值，以及划分方案、可行性判定、容量枚举）。
第二段预留给改造后的二分答案路径演示，待实现补齐。
"""

from binanswer.binanswer import BinaryAnswerKit


def demo_baseline():
    print("== 基线：逐个试答案的朴素路径 ==")
    k = BinaryAnswerKit()

    vals = [7, 2, 5, 10, 8]
    ans = k.minimize_max_segment_sum(vals, 2)
    print("最小化最大段和 =", ans, " 试答案次数 =", k.trials,
          " 判定次数 =", k.checks, " 线性操作数 =", k.ops)
    print("划分方案（段末下标）=", k.segment_plan(vals, 2))

    k.reset_counters()
    print("最大化最小段和 =", k.maximize_min_segment_sum([1, 2, 1, 2, 1], 3),
          " 试答案次数 =", k.trials)

    k.reset_counters()
    print("最小可行吃速 =", k.min_eating_speed([30, 11, 23, 4, 20], 6),
          " 试答案次数 =", k.trials)

    print("最小最大差值 =", k.min_max_pair_gap([1, 5, 3, 19]))

    k.reset_counters()
    print("bound=17 可行 =", k.feasible(vals, 2, 17),
          " bound=18 可行 =", k.feasible(vals, 2, 18))
    print("候选取值 =", k.candidate_bounds(vals))
    print("枚举首个可行 =", k.sweep_bound(vals, 2, [2, 5, 7, 8, 10, 18]),
          " 试答案次数 =", k.trials)

    print("空序列最小最大段和 =", k.minimize_max_segment_sum([], 0))
    print("全零序列划分 =", k.segment_plan([0, 0, 0], 2))
    print("两元素最小差值 =", k.min_max_pair_gap([4, 9]))


def demo_binary():
    # TODO: 第二段演示（实现后补）
    pass


def main():
    demo_baseline()
    demo_binary()


if __name__ == "__main__":
    main()
