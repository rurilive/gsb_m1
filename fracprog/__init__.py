"""fracprog：分数规划工具的朴素实现。

当前只有一条路：给定若干元素的收益与成本，求子集使收益之和与成本之和的比值最
大，全靠枚举全部选取组合再逐个算比值取极值，判断某比率是否可达也走同一条枚举老
路。见 fracprog.naive，二分答案加可行性判定与动态规划或贪心那两条做法见任务描述。
"""

from fracprog.naive import (
    Erro,
    RatioError,
    Tool,
    best_selection,
    best_selection_k,
    best_selection_with_deps,
    combination_count,
    is_reachable,
    naive_ratio,
    normalize_items,
    to_fraction,
)

__all__ = [
    "Erro",
    "RatioError",
    "Tool",
    "best_selection",
    "best_selection_k",
    "best_selection_with_deps",
    "combination_count",
    "is_reachable",
    "naive_ratio",
    "normalize_items",
    "to_fraction",
]
