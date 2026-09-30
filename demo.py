"""sccdag 演示脚本。

第一段：跑一遍基线功能（live，可直接运行）。
第二段：实现后补。
"""

from sccdag.graph import ReachGraph


def build_demo_graph():
    """构造一张含两个环、外加上一条单向链的小图。"""
    g = ReachGraph()
    for n in ("a", "b", "c", "d", "e"):
        g.add_node(n)
    # 环一：a 与 b 互达
    g.add_edge("a", "b")
    g.add_edge("b", "a")
    # 环二：c、d、e 三者互达
    g.add_edge("c", "d")
    g.add_edge("d", "e")
    g.add_edge("e", "c")
    # 单向桥：从环一到环二，反向不可达
    g.add_edge("b", "c")
    return g


def baseline_demo():
    g = build_demo_graph()
    print("节点:", g.nodes())
    print("边:", g.edges())
    print("a 的出度:", g.degree("a"))
    print("a 到 e 可达:", g.reachable("a", "e"))
    print("e 到 a 可达:", g.reachable("e", "a"))
    print("a 与 b 同分量:", g.same_component("a", "b"))
    print("a 与 c 同分量:", g.same_component("a", "c"))
    print("a 与 c 双向可达:", g.bidirectional("a", "c"))


def main():
    print("== 第一段：基线功能 ==")
    baseline_demo()
    print("== 第二段：强连通分量分解、缩点图与分量间可达 ==")
    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
