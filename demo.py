"""resvoir 现状演示。

第一段：往朴素全量保留的抽样器里流一串元素，看全部保留、累计流入计数、
样本等于全体、加权均值与分位、按标签分组，以及内存无界的标记；
第二段：预留的固定容量均匀与加权抽样演示位子（见文末注释）。
"""

from resvoir.buffer import KeepAll


def main():
    print("=== 朴素全量保留 ===")
    c = KeepAll()
    for item in range(1, 11):
        c.add(item, weight=1, label="even" if item % 2 == 0 else "odd")
    print("  累计流入 -> %d" % c.seen())
    print("  留住的元素 -> %s" % (c.items(),))
    print("  样本 -> %s" % (c.sample(),))
    print("  权重之和 -> %s" % c.total_weight())
    print("  加权均值 -> %s" % c.mean())
    print("  中位分位 -> %s" % c.quantile(0.5))
    print("  按标签分组 -> %s" % (c.by_label(),))
    print("  内存有界 -> %s" % c.is_bounded())
    c.add(100, weight=5, label="big")
    print("  再流一个重权元素后权重之和 -> %s" % c.total_weight())
    print("  留住的元素个数 -> %d（等于累计流入，内存随流入增长）" % len(c))

    # TODO(固定内存抽样): 在 resvoir 里补出容量为 k 的均匀蓄水池（Algorithm R 与
    # 按跳过数的 Algorithm L）、带权按比例选中的加权抽样（A-Res 或优先级键，可注入
    # 随机种子复现）、按标签分层的抽样（每层保 k 个或按比例分配）、样本上的总体均值
    # 与分位估计（带抽样误差）、两个同参数样本的合并（合并权重键），以及无论流入多少
    # 内存都固定为 O(k) 的界限之后，在这里加一段演示：先建一个容量为 k 的均匀蓄水池，
    # 流进远多于 k 个元素，打印样本大小与内存占用确认为 k，换固定种子再跑一遍确认
    # 样本逐项一致；再建一个加权抽样器，流进带不同权重的元素，打印各权重段被选中的
    # 频次比例，确认与权重比例相称；最后把两个同参数的样本合并，打印合并后的样本与
    # 单流一次得到的样本在统计量上一致。


if __name__ == "__main__":
    main()
