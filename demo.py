"""bridgecut 现状演示。

第一段：搭一张小图，用逐一删边删点再重判连通性的朴素实现，
看割边、割点、双连通分量与缩点桥树；
第二段：预留的一次遍历实现演示位子，见文末注释。
"""

from bridgecut.graph import UndirectedGraph


def main():
    print("=== 朴素删边删点重判 ===")
    edges = [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 5), (5, 3)]
    g = UndirectedGraph(6, edges)
    print("  结点数 %d，边数 %d" % (g.node_count(), g.edge_count()))
    print("  是否连通 %r" % (g.is_connected(),))
    print("  割边（编号） %s" % (g.bridges(),))
    print("  割点（编号） %s" % (g.articulation_points(),))
    print("  边双连通分量 %s" % (g.edge_components(),))
    print("  点分量 %s" % (g.vertex_components(),))
    print("  缩点桥树 %s" % (g.bridge_tree(),))
    print("  0 到 4 必经边 3 %r" % (g.must_pass_edge(0, 4, 3),))
    print("  0 到 4 必经点 2 %r" % (g.must_pass_node(0, 4, 2),))

    g.reset_counters()
    g.bridges()
    print("  求一次割边的计数 %s" % (g.counters(),))

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
