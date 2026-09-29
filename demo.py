"""lctlib 现状演示。

第一段：搭一片小森林，用邻接集合与当场遍历看连通性、路径和、子树和与
连通分量计数；
第二段：预留的动态树改造演示位子（见文末注释）。
"""

from lctlib.forest import FlatForest


def main():
    print("=== 朴素动态森林 ===")
    f = FlatForest()
    for node in range(1, 7):
        f.add_node(node)
    for u, v in [(1, 2), (2, 3), (2, 4), (5, 6)]:
        f.link(u, v)
    for node, value in {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6}.items():
        f.set_weight(node, value)

    print("  节点 %s，边数 %d" % (f.nodes(), f.edge_count()))
    print("  节点 2 的邻居 %s" % sorted(f.neighbors(2)))
    print("  1 与 4 连通吗 %s" % f.connected(1, 4))
    print("  1 与 5 连通吗 %s" % f.connected(1, 5))
    print("  3 到 4 的路径和 %d" % f.path_sum(3, 4))
    print("  以 2 为根、1 为整树根的子树和 %d" % f.subtree_sum(2, 1))
    print("  当前连通分量个数 %d" % f.component_count())

    f.cut(2, 4)
    print("  断掉 2-4 之后，1 与 4 连通吗 %s" % f.connected(1, 4))
    print("  断掉 2-4 之后，连通分量个数 %d" % f.component_count())

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
