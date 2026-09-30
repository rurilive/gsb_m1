"""NaiveKnapsack 现状演示。

第一段：朴素背包的装载上限、最大价值与可行组合个数。
第二段：预留的动态规划与对拍演示位子（见文末注释）。
"""

from knapsackdp.knapsack import NaiveKnapsack


def main():
    print("=== 朴素背包（现有能力） ===")
    weights = [1, 3, 4, 5]
    values = [1, 4, 5, 7]
    k = NaiveKnapsack(weights, values, 7)
    print("  容量 =", k.capacity)
    print("  物品数 =", len(k))
    print("  最大价值 =", k.max_value())
    print("  可行组合个数 =", k.count_combinations())

    # TODO: 第二段演示（实现后补）

    print("=== 边界约定 ===")
    empty = NaiveKnapsack([], [], 10)
    print("  空物品最大价值 =", empty.max_value())
    print("  空物品组合数 =", empty.count_combinations())
    zero_cap = NaiveKnapsack([1, 2], [5, 6], 0)
    print("  零容量最大价值 =", zero_cap.max_value())


if __name__ == "__main__":
    main()
