"""pathcover 演示脚本。

第一段：跑一遍基线能力（枚举顶点划分求最小路径覆盖、校验覆盖），可
直接运行；
第二段：实现后补（见文末注释）。
"""

from pathcover.covering import PathCoverer


def baseline_demo():
    g = PathCoverer()
    for u, v in [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")]:
        g.add_edge(u, v)

    print("点数:", g.node_count())
    print("边数:", g.edge_count())
    print("最小路径条数:", g.min_path_count())
    cover = g.min_path_cover()
    print("一个最小路径覆盖:", cover)
    print("覆盖是否合法:", g.is_valid_cover(cover))


def main():
    print("== 第一段：基线枚举能力 ==")
    baseline_demo()
    print("== 第二段：拆点建二分图求得的最小路径覆盖与匹配 ==")
    # TODO: 第二段演示（实现后补）
    # 实现后在这里补一段：换一张稍大的有向无环图，先跑拆点建二分图求
    # 最大匹配，打印匹配条数、最小路径覆盖条数，再打印覆盖方案，并用同
    # 一批数据把新老两条路的结果对一遍，确认条数与逐条路径都一致；再打
    # 印一次固定输入重复跑的结果，确认稳定。


if __name__ == "__main__":
    main()
