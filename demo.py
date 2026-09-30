"""matroid 现状演示。

第一段：用小规模数据演示现有的枚举式子集求解。
第二段：预留的迭代演示位子（见文末注释）。
"""

from matroid.core import (
    Element,
    Interval,
    Task,
    fractional_knapsack,
    integer_knapsack,
    is_independent,
    max_non_overlapping,
    max_profit_schedule,
    max_weight_independent,
)


def main():
    print("=== 最大权独立集（现有能力，枚举子集） ===")
    elems = [
        Element("a", size=1, weight=3),
        Element("b", size=2, weight=5),
        Element("c", size=3, weight=4),
        Element("d", size=1, weight=6),
    ]
    print("  独立判定(a,b,c) ->", is_independent(elems, elems[:3]))
    print("  最优独立集      ->", [x.label for x in max_weight_independent(elems)])

    print("=== 最多不重叠区间（枚举组合） ===")
    ivs = [Interval(1, 3), Interval(2, 4), Interval(5, 7), Interval(6, 8)]
    chosen = max_non_overlapping(ivs)
    print("  选择数:", len(chosen), "区间:", [(v.start, v.end) for v in chosen])

    print("=== 分数背包与整数背包（枚举组合） ===")
    items = [Element("a", size=2, weight=3), Element("b", size=1, weight=1)]
    print("  分数背包:", fractional_knapsack(items, 2)[0])
    print("  整数背包:", integer_knapsack(items, 2)[0])

    print("=== 截止期调度（枚举子集） ===")
    tasks = [
        Task("a", duration=1, deadline=1, weight=5),
        Task("b", duration=1, deadline=1, weight=4),
        Task("c", duration=1, deadline=2, weight=6),
    ]
    print("  最大收益任务组 ->", [t.label for t in max_profit_schedule(tasks)])

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
