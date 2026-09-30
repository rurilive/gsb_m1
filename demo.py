"""winx 现状演示。

第一段：用朴素实现跑一遍定长窗口的最大、最小、中位、和与不同元素个数。
第二段：预留的流式窗口工具集演示位子（见文末注释）。
"""

from winx.window import WindowStats


def main():
    values = [4, 1, 7, 1, 9, 2, 6, 3]
    size = 3
    stats = WindowStats(size)

    print("=== 朴素窗口统计（现有能力） ===")
    print("  序列       ->", values)
    print("  窗口大小   ->", size)
    print("  窗口最大值 ->", stats.maxima(values))
    print("  窗口最小值 ->", stats.minima(values))
    print("  窗口中位数 ->", stats.medians(values))
    print("  窗口和     ->", stats.sums(values))
    print("  不同元素数 ->", stats.distinct_counts(values))

    print("=== 朴素顺序统计 ===")
    print("  第0小      ->", stats.kth_smallest(values, 0))
    print("  第2小      ->", stats.kth_smallest(values, 2))
    print("  小于5的个数 ->", stats.rank(values, 5))

    print("=== 边界一路看 ===")
    print("  窗口为1    ->", WindowStats(1).maxima(values))
    print("  窗口等于长度 ->", WindowStats(len(values)).maxima(values))
    print("  窗口大于长度 ->", WindowStats(len(values) + 5).maxima(values))

    # TODO: 第二段演示（实现后补）
    # 说明：单调队列与有序结构就位后，在这里补一段演示——用单调双端队
    # 列一次扫描在线产出每个窗口的最大与最小，用两堆维护窗口内有序元素
    # 在线取中位，用前缀和与增量计数维护窗口和与不同元素数，再打印第k
    # 小与某值的排名，与上面的朴素结果逐项对齐，看单趟线性扫描的走法。


if __name__ == "__main__":
    main()
