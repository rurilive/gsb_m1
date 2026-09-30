"""slidewin 快速演示。

第一段跑改造前的基线能力（朴素和最短与和最长、至多不同字符的最长子串、恰好含若干
不同字符的子串个数、覆盖全部目标字符的最短窗口）。
第二段预留给改造后的双指针与窗口计数高效路径演示，待实现补齐。
"""

from slidewin.window import WindowStats


def demo_baseline():
    print("== 基线：朴素枚举路径 ==")
    k = WindowStats()

    seq = [2, 3, 1, 2, 4, 3]
    s = k.sum_bounds(seq, 7)
    print("和不小于七的最短长度 =", s.short_len, " 和不大于七的最长长度 =", s.long_len)
    print("本次扫描元素次数 =", s.scan)

    d = k.longest_distinct("abcba", 2)
    print("至多两个不同字符的最长子串长度 =", d.length, " 左端 =", d.left)

    c = k.distinct_count("aab", 2)
    print("恰好含两个不同字符的子串个数 =", c)

    e = k.distinct_count("aab", 1)
    print("恰好含一个不同字符的子串个数 =", e)

    w = k.cover_window("abcde", "bd")
    print("覆盖目标字符的最短窗口 =", w)

    print("空序列的和最短长度 =", k.sum_bounds([], 5).short_len)


def demo_optimized():
    # TODO: 第二段演示（实现后补）
    pass


def main():
    demo_baseline()
    demo_optimized()


if __name__ == "__main__":
    main()
