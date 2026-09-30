"""graphx 现状演示。

第一段：朴素路径——反复删点删边重扫全图，求割点割边与强连通分量。
第二段：以一次深度优先搜索为核心的新路径演示位（见文末注释）。
"""

from graphx import Graph


def build_demo_graph():
    graph = Graph()
    graph.add_edge(1, 2)
    graph.add_edge(2, 3)
    graph.add_edge(3, 1)
    graph.add_edge(3, 4)
    graph.add_node(5)
    return graph


def main():
    graph = build_demo_graph()
    print("=== 朴素路径：逐点逐边重扫 ===")
    print(f"  节点 -> {graph.nodes()}")
    print(f"  边   -> {graph.edges()}")
    print(f"  连通分量 -> {graph.connected_components()}")
    print(f"  分量个数 -> {graph.component_count()}")
    print(f"  割点 -> {graph.split_vertices()}")
    print(f"  割边 -> {graph.bridges()}")
    print(f"  非割边 -> {graph.bidirectional_edges()}")
    print(f"  强连通分量 -> {graph.scc()}")
    print(f"  全图重扫次数 -> {graph.sweep_count()}")

    # TODO(一次深度优先搜索): 把连通性、割点割边、强连通分量、缩点、拓扑序与
    # 双路径互达边都改成以一次深度优先搜索为核心——用进入时间与追溯值一次判出
    # 割点割边，用栈与时间戳一次求强连通分量，再缩点成有向无环图并给出拓扑序。
    # 实现后在这里加一段演示：用同一张图跑新路径，打印割点割边集合、分量划分、
    # 缩点图与拓扑序，并打印遍历次数与朴素路径逐点逐边重扫次数的差距。


if __name__ == "__main__":
    main()
