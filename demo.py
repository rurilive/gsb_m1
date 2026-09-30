"""digitcount 快速演示。

第一段跑改造前的基线能力（四条区间计数的逐数枚举、求具体数的最小值，以及
两条独立慢速做法与主路径的逐项对账、逐数判定次数随区间放大的规模对照）。
第二段预留给改造后的数位 DP 演示，待实现补齐。
"""

from digitcount.count import IntervalCounter


def demo_baseline():
    print("== 基线：逐数枚举四条区间计数 ==")
    c = IntervalCounter()
    print("零到一千不含数字七的个数 =", c.count_without_digit(7, 0, 1000),
          "逐数判定次数 =", c.enumerate_visits)
    print("零到一千各位数字和为九的个数 =", c.count_digit_sum(9, 0, 1000),
          "逐位访问次数 =", c.digit_visits)
    print("零到一千相邻两位严格递增的个数 =", c.count_strict_increasing(0, 1000),
          "逐位访问次数 =", c.digit_visits)
    print("一百到一千为七之整数倍的个数 =", c.count_multiple(7, 100, 1000),
          "逐数判定次数 =", c.enumerate_visits)

    print("== 基线：求区间内满足条件的最小具体数 ==")
    print("一百到一万不含数字七的最小者 =", c.find_minimum("without_digit", 7, 100, 10000))
    print("一百到一万各位和为十的最小者 =", c.find_minimum("digit_sum", 10, 100, 10000))
    print("一百到一万相邻严格递增的最小者 =", c.find_minimum("strict_increasing", None, 100, 10000))
    print("一百到一万为七之整数倍的最小者 =", c.find_minimum("multiple", 7, 100, 10000))

    print("== 基线：独立慢速做法与主路径逐项对账 ==")
    pairs = [
        ("without_digit", 7),
        ("digit_sum", 9),
        ("strict_increasing", None),
        ("multiple", 7),
    ]
    for condition, arg in pairs:
        main = IntervalCounter().find_minimum(condition, arg, 20, 500)
        indep = IntervalCounter().independent_minimum(condition, arg, 20, 500)
        print("条件 %s：主路径最小者 %r，独立路最小者 %r" % (condition, main, indep))

    print("== 基线：规模对照 ==")
    for high in (100, 1000, 10000):
        probe = IntervalCounter(0, high)
        probe.count_without_digit(7)
        print("区间零到 %d：逐数判定 %d 次，数位状态访问 %d 次"
              % (high, probe.enumerate_visits, probe.state_visits))


def demo_optimized():
    # TODO: 第二段演示（实现后补）
    pass


def main():
    demo_baseline()
    demo_optimized()


if __name__ == "__main__":
    main()
