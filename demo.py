"""SortedBag 现状演示。

第一段：建集合、插入、查找、前驱后继、排名、下标取值、区间扫描、删除。
第二段：预留的跳表工具集演示位子（见文末 TODO 注释）。
"""

from skipx.sortedbag import NotFoundError, SortedBag


def main():
    print("=== 有序多重集合（排序数组） ===")
    bag = SortedBag([5, 1, 3, 3, 2])
    print("  items        = %s" % (bag.items(),))
    print("  len          = %d" % len(bag))
    print("  find(3)      = %s" % bag.find(3))
    bag.insert(4)
    bag.insert(3)
    print("  插入 4,3 后  = %s" % (bag.items(),))
    print("  rank(3)      = %d" % bag.rank(3))
    print("  at(2)        = %s" % bag.at(2))
    print("  predecessor(4) = %s" % bag.predecessor(4))
    print("  successor(4)   = %s" % bag.successor(4))
    print("  range(2, 4)  = %s" % (bag.range_scan(2, 4),))
    print("  查找 5 的比较次数 = %d" % bag.probe_count(5))
    bag.remove(3)
    print("  remove(3) 后 = %s" % (bag.items(),))
    try:
        bag.predecessor(1)
    except NotFoundError as exc:
        print("  前驱不存在 -> %s" % type(exc).__name__)

    # TODO(跳表改造): skipx 里补出以跳表为核心的有序工具集之后，在这里加第二段演示：
    # 用固定种子建出多层索引，查找从最高层逐层下降到最底层；插入删除维护各级前向指针，
    # 打印查找经过的层数与结点数，并与上面的 SortedBag 在同一批数据上逐项对照，
    # 说明查找、前驱后继、按下标取值、排名两边结果一致而跳表下降结点数更少。


if __name__ == "__main__":
    main()
