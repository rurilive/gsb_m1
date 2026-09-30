"""dsu 现状演示。

第一段：登记若干元素，做几次合并与查询，看朴素改名口径给出的分组、连通性、
带权偏移、动态连通性下的环检测与规模计数。
第二段：预留的迭代演示位子（见文末注释）。
"""

from dsu.core import NaiveDisjointSets


def main():
    print("=== 不相交集合与动态连通性（现有朴素能力） ===")
    uf = NaiveDisjointSets()
    for x in range(6):
        uf.add(x)
    print("  登记元素:", uf.elements())
    uf.union(0, 1)
    uf.union(2, 3)
    uf.union(1, 2)
    print("  合并后连通 0 与 3:", uf.connected(0, 3))
    print("  各集合:", uf.groups())
    print("  组件个数:", uf.component_count(), " 大小:", uf.component_sizes())
    print("  0 所在集合大小:", uf.size(0))

    uf.union_weighted(4, 5, 7)
    print("  4 相对 5 的偏移:", uf.relate(4, 5))

    cyc = NaiveDisjointSets()
    cyc.add_edge(0, 1)
    cyc.add_edge(1, 2)
    print("  连 0 与 2 是否成环:", cyc.would_close_cycle(0, 2))
    print("  动态加边 0 与 2 并入成功:", cyc.add_edge(0, 2))

    print("  累计合并次数:", uf.count_merges())
    print("  累计查询次数:", uf.count_queries())
    print("  累计改名次数:", uf.count_renames())

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
