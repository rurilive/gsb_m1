"""domtree 现状演示。

第一段：建一张并行分叉再汇合的小有向图，用逐点删点判可达的朴素路子看
起点可达集合、删一点之后的可达集合、全部支配点、直接支配点与支配树边；
第二段：预留的线性支配树改造演示位子（见文末注释）。
"""

from domtree.dominator import DirectedGraph


def main():
    print("=== 朴素支配关系（逐点删点判可达） ===")
    g = DirectedGraph(
        nodes=["s", "a", "b", "c", "d", "e", "f"],
        edges=[("s", "a"), ("s", "b"), ("s", "c"),
               ("a", "d"), ("b", "d"), ("c", "d"),
               ("d", "e"), ("e", "f")],
    )
    print("  起点 s 可达 %s" % sorted(g.reachable_from("s")))
    print("  删去 d 之后可达 %s" % sorted(g.reachable_without("s", "d")))
    print("  各点全部支配点 %s" % g.dominators("s"))
    print("  各点直接支配点 %s" % g.immediate_dominators("s"))
    print("  支配树边 %s" % g.dominator_edges("s"))
    print("  d 支配 f 吗 %s" % g.dominates("s", "d", "f"))
    print("  a 支配 f 吗 %s" % g.dominates("s", "a", "f"))
    print("  s 的直接孩子 %s" % g.children_of("s", "s"))

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
