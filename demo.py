"""fracprog 现状演示。

第一段：几组小规模元素走一遍现有朴素能力，看元素归一、枚举全部选取组合取到的最
优比率与选取方案、恰好 k 个元素的最优、带依赖的选取最优、某比率是否可达，以及
枚举组合次数随元素数指数上涨的规模对照；顺带看成本为零与 k 越界的诊断。
第二段：预留的二分答案加可行性判定路、动态规划或贪心路、两个独立能力以及枚举组
合次数与二分判定次数对照的演示位子。
"""

from fractions import Fraction

from fracprog import (
    RatioError,
    Tool,
    best_selection,
    best_selection_k,
    best_selection_with_deps,
    combination_count,
    is_reachable,
    normalize_items,
)

ITEMS = [(2, 1), (3, 1), (1, 1)]
DEPS = [None, 0]


def main():
    print("=== 最优比率工具的朴素实现 ===")
    print("  元素(收益, 成本):", ITEMS)
    print("  归一为分数:", normalize_items(ITEMS))

    result = best_selection(ITEMS)
    print("  最优比率:", result["ratio"], " 选取方案:", result["selection"],
          " 枚举组合数:", result["count"])
    print("  恰好 2 个的最优比率:", best_selection_k(ITEMS, 2))
    print("  带依赖的最优比率:", best_selection_with_deps([(1, 1), (5, 1)], DEPS))
    print("  比率 3 是否可达:", is_reachable(ITEMS, Fraction(3))["reachable"],
          " 比率 4 是否可达:", is_reachable(ITEMS, Fraction(4))["reachable"])

    tool = Tool(ITEMS)
    tool.best_selection()
    print("  工具累计枚举组合次数:", tool.enumeration_count())
    tool.reset_count()
    print("  清零后:", tool.enumeration_count())

    for count in (4, 8, 16):
        print("  元素数", count, "朴素枚举组合总数:", combination_count(count))

    try:
        best_selection_k(ITEMS, 4)
    except RatioError as exc:
        print("  k 越界诊断:", str(exc))

    try:
        best_selection([(1, 0)])
    except RatioError as exc:
        print("  成本为零诊断:", str(exc))

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
