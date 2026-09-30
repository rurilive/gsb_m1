"""invx 现状演示。

第一段：用朴素实现做一轮逆序对、正序对与相等对计数，看基线能力。
第二段：预留的迭代演示位子（见文末注释）。
"""

from invx.inv import (
    Values,
    count_equal_pairs,
    count_inversions,
    count_ordered_pairs,
    distinct_count,
    kth_smallest,
    rank_of,
    total_pairs,
)

DATA = [5, 1, 4, 2, 3]


def main():
    print("=== 朴素统计：三类下标对计数 ===")
    print(f"  序列           -> {DATA}")
    inv = count_inversions(DATA)
    ordered = count_ordered_pairs(DATA)
    equal = count_equal_pairs(DATA)
    print(f"  逆序对         -> {inv}")
    print(f"  正序对         -> {ordered}")
    print(f"  相等对         -> {equal}")
    print(f"  三者和         -> {inv + ordered + equal}，下标对总数 -> {total_pairs(DATA)}")

    print("=== 朴素统计：边界形态 ===")
    print(f"  递增           -> {count_inversions([1, 2, 3, 4])}")
    print(f"  递降           -> {count_inversions([4, 3, 2, 1])}")
    print(f"  全相等         -> {count_inversions([7, 7, 7, 7])}")
    print(f"  含重复         -> {count_inversions([2, 4, 1, 3, 5])}")

    print("=== 朴素统计：排序后线性扫描 ===")
    print(f"  不同取值       -> {distinct_count(DATA)}")
    print(f"  第几小         -> {kth_smallest(DATA, 3)}")
    print(f"  排名查询       -> {rank_of(DATA, 3)}")

    print("=== 朴素统计：统计器摘要 ===")
    values = Values(DATA)
    for key, value in values.summary().items():
        print(f"  {key:<15}-> {value}")

    # TODO: 第二段演示（实现后补）
    # 说明：归并与树状数组两条路径改造完成后，在这里补一段演示——对上面同一
    # 条固定序列，分别走归并计数与树状数组计数，逐项断言两条路给出的逆序对、
    # 正序对与相等对完全一致，再与上面这条朴素枚举口径对照，并打印归并的递归
    # 层数与树状数组的访问计数，让新路径能直接跑通并正常退出。


if __name__ == "__main__":
    main()
