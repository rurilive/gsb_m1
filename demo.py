"""treecover 现状演示。

第一段：朴素求解——枚举全部顶点子集，逐个检查是否满足覆盖或独立要求，
求出最小支配集、最小点覆盖、最大独立集，并打印子集检查的次数。
第二段：预留的三条独立做法与规模对照演示位子（见文末注释）。
"""

from treecover import (
    Tree,
    max_independent_set,
    min_dominating_set,
    min_vertex_cover,
    max_weight_independent_set,
    subset_check_count,
    weighted_min_dominating_set,
)


def build_sample():
    """一段样例：根 1，一条主链 1-2-3-4，3 号上挂两个叶子 5、6。"""
    t = Tree(1)
    t.add_edge(1, 2)
    t.add_edge(2, 3)
    t.add_edge(3, 4)
    t.add_edge(3, 5)
    t.add_edge(3, 6)
    return t


def main():
    t = build_sample()
    print("=== 朴素求解（枚举全部顶点子集逐个检查） ===")
    print(f"  顶点 {t.vertices()}，边 {t.edges()}")
    print(f"  求一次最小支配集要检查 {subset_check_count(t)} 个子集")

    size, chosen = min_dominating_set(t)
    print(f"  最小支配集大小 {size}，方案 {chosen}")

    size, chosen = min_vertex_cover(t)
    print(f"  最小点覆盖大小 {size}，方案 {chosen}")

    size, chosen = max_independent_set(t)
    print(f"  最大独立集大小 {size}，方案 {chosen}")

    weights = {1: 3, 2: -1, 3: 2, 4: 0, 5: 1, 6: 1}
    cost, chosen = weighted_min_dominating_set(t, weights)
    print(f"  带权最小支配集总权 {cost}，方案 {chosen}")
    cost, chosen = max_weight_independent_set(t, weights)
    print(f"  最大权独立集总权 {cost}，方案 {chosen}")

    # TODO: 第二段演示（实现后补）
    # 树形动态规划（三状态：自选、被父选、被子选）求最小支配集、贪心法（从
    # 叶向上，未覆盖就让其父覆盖）、独立树形动态规划求最小点覆盖与最大独立集
    # 三条互不调用的做法补齐后，在这里加一段演示：同一棵树上把三路结果与小规
    # 模枚路子集路逐项打印对照；顺带打印朴素子集检查次数与树形动态规划状态转
    # 移次数的规模对照。


if __name__ == "__main__":
    main()
