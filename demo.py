"""minrot 现状演示。

第一段：用逐起点枚举求最小与最大字典序循环旋转，判定两串是否循环
同构并求最短位移，打印朴素比较次数；
第二段：预留的线性最小表示法等演示位子（见文末注释）。
"""

from minrot.naive import (
    RotTools,
    is_rotation,
    max_rotation,
    min_rotation,
    min_rotation_index,
    min_shift,
)


def main():
    print("=== 朴素逐起点枚举 ===")
    text = "baba"
    tools = RotTools(text)
    print("  串 %s" % text)
    print("  最小表示起点 %d" % min_rotation_index(text))
    print("  最小旋转串 %s" % min_rotation(text))
    print("  最大旋转串 %s" % max_rotation(text))

    tools.reset_compare_count()
    tools.min_rotation_index()
    print("  朴素枚举最小表示比较次数 %d" % tools.compare_count())
    print("  与 bca 同构 %s" % is_rotation("abc", "bca"))
    print("  由 abc 到 cab 的最短位移 %d" % min_shift("abc", "cab"))

    # TODO: 第二段演示（实现后补）
    #
    # 补出线性最小表示法之后，在这里加一段演示：对同一批串用最小表示法
    # 求起点下标与最小旋转串，再用最大表示法求最大旋转串，再用自身拼接
    # 后找原串首次出现求最小旋转，再用两串拼接分别求最小表示判循环同构，
    # 三路对同一批串逐项对照并与上面朴素枚举一致；打印最小表示法的比较
    # 次数与朴素比较次数的规模差距；最后覆盖空串、单字符、全相同字符、
    # 严格递增、严格递减、含重复最小前缀、长度不等、不可同构、含特殊字符
    # 这些边界，确认各条路径结论一致。

    print("  朴素判定 abab 与 baba 同构 %s"
          % is_rotation("abab", "baba"))


if __name__ == "__main__":
    main()
