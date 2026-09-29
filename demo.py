"""graphx 现状演示。

第一段：在朴素有向图上做遍历。
第二段：预留的迭代演示位子（见文末注释）。
"""

from graphx.net import FlatNet


def main():
    print("=== 朴素有向图遍历（现有能力） ===")
    g = FlatNet()
    g.add_edge("s", "a", 3)
    g.add_edge("s", "b", 2)
    g.add_edge("a", "t", 1)
    g.add_edge("b", "t", 4)
    print(f"  nodes()        -> {g.nodes()}")
    print(f"  node_count()   -> {g.node_count()}")
    print(f"  edges()        -> {g.edges()}")
    print(f"  neighbors(s)   -> {g.neighbors('s')}")
    print(f"  out_degree(s)  -> {g.out_degree('s')}")
    print(f"  reachable(s,t) -> {g.reachable('s', 't')}")
    print(f"  bfs_order(s)   -> {g.bfs_order('s')}")

    # TODO: 第二段演示（实现后补）。
    # 实现后在这里补一轮最大流、最小割与二分图匹配的演示：
    # 先在一张带容量的有向图上算源到汇的最大流并打印流值，
    # 再由残量网络导出最小割并打印割容量，确认割容量等于最大流值，
    # 最后把一张二分图转成流求最大匹配并打印匹配对数。


if __name__ == "__main__":
    main()
