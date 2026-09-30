"""knapsackx 现状演示。

第一段：朴素布尔容量表逐格填写，得到可达重量集合与最优价值。
第二段：预留的整数位集整体推进演示位子（见文末注释）。
"""

from knapsackx import Knapsack


def main():
    print("=== 朴素布尔容量表求可达重量与最优价值 ===")
    knap = Knapsack([(3, 4), (5, 6), (7, 8)])
    print(f"  物品 {knap.items()}")
    print(f"  容量 15 的可达重量 -> {knap.reachable_set(15)}")
    print(f"  容量 15 的最优价值 -> {knap.best_value(15)}")
    print(f"  容量 15 的最优方案 -> {knap.plan_value(15)}")
    print(f"  恰好装满 12 -> {knap.exact_fit(12)}")
    print(f"  逐格更新次数 -> {knap.update_count()}")

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
