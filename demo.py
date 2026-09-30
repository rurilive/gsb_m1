"""mcmf 现状演示。

第一段：建一张小图，看朴素最大流与它的累加费用。
第二段：预留的迭代演示位子（见文末注释）。
"""

from mcmf.flow import MinCostFlow


def main():
    print("=== 朴素最大流（现有能力） ===")
    ctx = MinCostFlow()
    ctx.add_edge("s", "a", 1, 0)
    ctx.add_edge("a", "t", 1, 50)
    ctx.add_edge("s", "b", 1, 0)
    ctx.add_edge("s", "c", 1, 0)
    ctx.add_edge("a", "c", 1, 0)
    ctx.add_edge("c", "t", 1, 0)
    ctx.add_edge("b", "t", 1, 0)
    ctx.max_flow("s", "t")
    print(f"  最大流值   -> {ctx.flow_value()}")
    print(f"  累加费用   -> {ctx.flow_cost()}")
    for u, v, cap, cost, flow in ctx.edge_flows():
        print(f"  {u}->{v} cap={cap} cost={cost} flow={flow}")

    # TODO: 第二段演示（实现后补）

if __name__ == "__main__":
    main()
