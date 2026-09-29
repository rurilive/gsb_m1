"""SortedMap 现状演示。

第一段：插入、按键查找、删除、左闭右开区间扫描。
第二段：预留的跳表演示位子（见文末 TODO 注释）。
"""

from skippy.sortedmap import SortedMap


def main():
    print("=== 有序映射（排序数组） ===")
    m = SortedMap()
    for k in (5, 1, 4, 2, 3):
        m[k] = k * k
    print("  keys       = %s" % (m.keys(),))
    print("  m[4]       = %s" % (m[4],))
    print("  get(9)     = %s" % (m.get(9),))
    print("  range(2, 5)= %s" % (m.range(2, 5),))
    print("  first      = %s" % (m.first(),))
    del m[3]
    print("  del 3,keys = %s" % (m.keys(),))

    # TODO(跳表改造): skippy 里补出有序映射的跳表（多层索引、可注入种子的随机层高）之后，
    # 在这里加第二段演示：注入固定 seed 复现各节点的层高分布、展示当前层数与元素数的自洽，
    # 再用 range 按键升序返回区间内的键值对、用 rank 与 select 互为逆地取出第 i 个键值，
    # 并与上面的 SortedMap 在同一批操作上对拍，说明两者顺序与结果一致。


if __name__ == "__main__":
    main()
