"""slopex 现状演示。

第一段：用平方枚举的朴素实现跑一遍两种代价策略下的最优划分。
第二段：预留的斜率优化工具集演示位子（见文末注释）。
"""

from slopex.quadratic import SegmentPlanner


def main():
    values = [4, 1, 7, 1, 9, 2, 6, 3]

    print("=== 朴素划分型动态规划（现有能力） ===")
    print("  序列           ->", values)

    square = SegmentPlanner("square", 2)
    print("  平方代价策略   ->")
    print("    最优总代价   ->", square.best_partition(values))
    print("    前缀代价表   ->", square.best_partitions(values))
    print("    最优切点     ->", square.best_cut_points(values))

    position = SegmentPlanner("position", 2)
    print("  起点代价策略   ->")
    print("    最优总代价   ->", position.best_partition(values))
    print("    前缀代价表   ->", position.best_partitions(values))
    print("    最优切点     ->", position.best_cut_points(values))

    print("=== 平方枚举的比较次数 ===")
    for n in (4, 8, 16, 32):
        print("  规模 %2d 的比较次数 -> %d" % (n, square.compare_count(n)))

    print("=== 边界一路看 ===")
    print("  空序列         ->", square.best_partition([]))
    print("  单元素         ->", square.best_partition([5]), position.best_partition([5]))
    print("  两个元素       ->", square.best_partition([1, 2]), position.best_partition([1, 2]))
    print("  全零序列       ->", square.best_partitions([0, 0, 0]))
    print("  开销为零       ->", SegmentPlanner("square", 0).best_partitions(values))

    # TODO: 第二段演示（实现后补）
    # 说明：下凸壳与单调指针就位后，在这里补一段演示——把两种代价的转移
    # 整理成含自变量斜率的直线形式，用凸壳维护候选转移并用单调指针均摊取
    # 最优，打印每个前缀的最优值与最优切点，与上面的平方枚举结果逐项对齐，
    # 同时打印凸壳比较次数与平方枚举次数的差距，看复杂度从平方降到近线性。


if __name__ == "__main__":
    main()
