"""intervaldp 快速演示。

第一段跑改造前的基线能力（朴素合并代价、最优划分、括号匹配）。
第二段预留给改造后的按区间长度递推的高效路径演示，待实现补齐。
"""

from intervaldp.interval import IntervalKit


def demo_baseline():
    print("== 基线：朴素枚举路径 ==")
    k = IntervalKit()

    stones = [4, 1, 1, 4]
    cost = k.merge_cost(stones)
    print("石子合并最小代价 =", cost, " 分裂点枚举次数 =", k.split_visits)

    print("最优分裂点 =", k.best_split(stones))

    text = ")()())"
    n = k.longest_valid(text)
    print("最长合法子串长度 =", n, " 逐字符扫描次数 =", k.char_visits)

    print("最少添加括号数 =", k.min_add("([)]"))

    print("已完全匹配的最少添加数 =", k.min_add("()[]{}"))
    print("全部相同石子的代价 =", k.merge_cost([3, 3, 3]))


def demo_optimized():
    # TODO: 第二段演示（实现后补）
    pass


def main():
    demo_baseline()
    demo_optimized()


if __name__ == "__main__":
    main()
