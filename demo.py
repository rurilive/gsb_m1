"""halfenum 现状演示。

第一段：位掩码全枚举下的几种子集搜索能力，附枚举规模。
第二段：预留的折半枚举与双向搜索演示位子（见文末注释）。
"""

from halfenum import (
    count_achievable_sums,
    group_difference,
    max_subset_sum,
    naive_enumeration_count,
    subset_sum_solution,
)


def main():
    print("=== 子集搜索（现有能力） ===")
    values = [3, 7, 2, 8, 5]
    print("  集合:", values)
    print("  枚举规模 2 的 n 次方:", naive_enumeration_count(len(values)))
    print("  容量 12 内的最大子集和:", max_subset_sum(values, 12))
    print("  凑成 15 的字典序最小方案:", subset_sum_solution(values, 15))
    print("  凑成 4 的结果:", subset_sum_solution(values, 4))
    print("  可达子集和个数:", count_achievable_sums(values))
    print("  两组和之差最小:", group_difference([1, 2, 3, 4], "min"))
    print("  两组和之差最大:", group_difference([1, 2, 3, 4], "max"))

    # 把 n 拉到二十，位掩码要检查的子集数
    print("  n 为 20 时的枚举规模:", naive_enumeration_count(20))

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
