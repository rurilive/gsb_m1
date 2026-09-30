"""dagtopo 现状演示。

第一段：搭一张小的依赖图，用反复线性扫描找零入度点的朴素实现，
看拓扑序、最早开始时间、关键路径、环的判定与可达计数；
第二段：预留的一次入度队列实现演示位子，见文末注释。
"""

from dagtopo.graph import DirectedGraph


def main():
    print("=== 朴素反复线性扫描 ===")
    edges = [(0, 2), (1, 2), (2, 3), (2, 4), (3, 5), (4, 5)]
    g = DirectedGraph(6, edges)
    print("  点数 %d，边数 %d" % (g.node_count(), g.edge_count()))
    print("  是否有环 %r" % (g.has_cycle(),))
    print("  拓扑序 %s" % (g.topological_order(),))
    durations = [3, 2, 4, 1, 5, 2]
    print("  最早开始时间 %s" % (g.earliest_start(durations),))
    print("  关键路径 %s" % (g.critical_path(durations),))
    print("  能到达的点数 %s" % (g.reachable_counts(),))
    print("  能被到达的点数 %s" % (g.reverse_reachable_counts(),))

    cg = DirectedGraph(4, [(0, 1), (1, 2), (2, 3), (3, 1)])
    print("  环上的点 %s" % (cg.cycle_nodes(),))

    g.reset_counters()
    g.topological_order()
    print("  求一次拓扑序的计数 %s" % (g.counters(),))

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
