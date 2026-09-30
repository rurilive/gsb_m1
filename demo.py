"""lctx 现状演示。

第一段：搭一片小森林，用邻接集合与当场遍历看连通性、路径和与最值、换根、
子树和与连通分量计数；
第二段：预留的动态树改造演示位子（见文末注释）。
"""

from lctx.dtree import Dtree


def main():
    print("=== naive dynamic forest ===")
    f = Dtree()
    for node in range(1, 7):
        f.add_node(node)
    for u, v in [(1, 2), (2, 3), (2, 4), (5, 6)]:
        f.link(u, v)
    for node, value in {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6}.items():
        f.set_weight(node, value)

    print("  nodes %s, edges %d" % (f.nodes(), f.edge_count()))
    print("  neighbors of 2 %s" % sorted(f.neighbors(2)))
    print("  connected 1-4 %s" % f.connected(1, 4))
    print("  connected 1-5 %s" % f.connected(1, 5))
    print("  path sum 3->4 %d" % f.path_sum(3, 4))
    print("  path max 3->4 %d" % f.path_max(3, 4))
    print("  subtree sum at 2 rooted 1 %d" % f.subtree_sum(2, 1))
    print("  components %d" % f.component_count())

    f.make_root(3)
    print("  after make_root(3), root of 1 is %d" % f.component_root(1))

    f.cut(2, 4)
    print("  after cut 2-4, connected 1-4 %s" % f.connected(1, 4))
    print("  after cut 2-4, components %d" % f.component_count())

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
