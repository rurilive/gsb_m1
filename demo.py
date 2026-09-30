"""sccond 现状演示。

第一段：朴素连通性——对每一对顶点各跑一次可达搜索求强连通分量，再在缩点
图上求拓扑序、最长链、源汇分量，并做整图强连通判断、分量间可达与最大可达
分量统计，最后打出逐对搜索次数与访问次数；
第二段：预留的三路独立分解、迭代实现与规模对照演示位子，见文末注释。
"""

from sccond import Digraph, naive_pair_count


def build_sample():
    """一段样例：两个三元环，2 到 3 一条单向边，缩点后是一条两节点的链。"""
    g = Digraph([0, 1, 2, 3, 4, 5])
    for u, w in [(0, 1), (1, 2), (2, 0), (3, 4), (4, 3), (2, 3), (5, 5)]:
        g.add_edge(u, w)
    return g


def main():
    g = build_sample()
    g.reset_counters()
    comps = g.components()
    print("=== 朴素逐对可达搜索（基线） ===")
    print("  顶点 %s，边数 %d" % (g.vertices(), g.edge_count()))
    print("  强连通分量 %s，共 %d 块" % (comps, g.component_count()))
    print("  整图强连通 %r" % (g.is_strongly_connected(),))
    print("  每点分量 %s" % {v: g.component_of(v) for v in g.vertices()})

    print("  缩点图顶点 %s" % (g.condensation().vertices(),))
    print("  拓扑序 %s" % (g.topological_order(),))
    length, path = g.longest_chain()
    print("  最长链长度 %d，一条最长链 %s" % (length, path))
    print("  源分量 %s，汇分量 %s" % (g.source_components(), g.sink_components()))
    print("  从 1 可达的分量 %s" % (g.reachable_components(1),))
    print("  点 0 可达的最大分量顶点数 %d" % (g.max_reachable_component_size(0),))
    print("  逐对搜索次数 %d，访问次数 %d" % (
        g.counters()["search_runs"], g.counters()["visit_count"]))
    print("  六点图朴素有序点对搜索上界 %d" % (naive_pair_count(6),))

    empty = Digraph()
    print("  空图分量 %s，强连通 %r" % (empty.components(), empty.is_strongly_connected()))

    # TODO: 第二段演示（实现后补）
    # 三路独立分解（时间戳加栈一趟、正反图两趟、迭代而非递归）互相印证、
    # 基于分量的拓扑序与最长链、整图强连通与分量间可达与最大可达分量顶点数
    # 都补齐后，在这里加一段演示：同一批图上把三路分量划分逐项对照；打出
    # 朴素逐对搜索次数与一趟分解访问次数，给出规模对照。


if __name__ == "__main__":
    main()
