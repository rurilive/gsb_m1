"""pushrelabel 现状演示。

第一段：建一张小网络，用现有朴素实现求最大流与最小割，看值是否相等。
第二段：预留的预流推进演示位子（见文末注释）。
"""

from pushrelabel import FlowNetwork, max_flow, min_cut


def build():
    """一张五节点的小网络，最大流为 5。"""
    net = FlowNetwork()
    net.add_edge("s", "a", 3)
    net.add_edge("s", "b", 2)
    net.add_edge("a", "b", 1)
    net.add_edge("a", "t", 2)
    net.add_edge("b", "t", 3)
    return net


def main():
    print("=== 朴素增广路最大流与最小割（现有能力） ===")
    net = build()
    flow = max_flow(net, "s", "t")
    print("  最大流值  =", flow.value)
    print("  增广次数  =", flow.augmentations)
    print("  各边流量  =",
          [(e.src, e.dst, e.flow) for e in flow.edges])

    cut = min_cut(net, "s", "t")
    print("  最小割值  =", cut.value)
    print("  源点侧    =", cut.source_side)
    print("  汇点侧    =", cut.sink_side)
    print("  割边      =", [(e.src, e.dst, e.capacity) for e in cut.cut_edges])
    print("  两值一致  =", flow.value == cut.value)

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
