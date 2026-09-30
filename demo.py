"""lisx 快速演示。

第一段跑改造前的基线能力（朴素长度、个数、重建）。
第二段预留给改造后的二分数尾高效路径演示，待实现补齐。
"""

from lisx.lis import LisKit


def demo_baseline():
    print("== 基线：朴素平方路径 ==")
    k = LisKit()

    seq = [10, 9, 2, 5, 3, 7, 101, 18]
    n = k.length(seq)
    print("严格上升长度 =", n, " 比较次数 =", k.comparisons)

    dup = [2, 2, 3, 3, 1]
    print("严格上升长度 =", k.length(dup, "strict"))
    print("非下降长度 =", k.length(dup, "nondecreasing"))

    order, vals = k.rebuild(seq)
    print("一条方案下标 =", order, " 取值 =", vals)
    print("重建比较次数 =", k.rebuild_comparisons)

    small = [1, 2, 3]
    print("上升子序列个数（全升）=", k.count(small))
    print("上升子序列个数（严格递减）=", k.count([3, 2, 1]))


def demo_optimized():
    # TODO: 第二段演示（实现后补）
    pass


def main():
    demo_baseline()
    demo_optimized()


if __name__ == "__main__":
    main()
