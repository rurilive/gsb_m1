"""blossom 演示脚本。

第一段：跑一遍基线能力（回溯枚举求最大匹配、判定完美匹配、回查配
对），可直接运行；
第二段：实现后补（见文末注释）。
"""

from blossom.matching import GraphMatcher


def baseline_demo():
    m = GraphMatcher()
    for u, v in [("a", "b"), ("a", "c"), ("b", "c"), ("c", "d"), ("d", "e")]:
        m.add_edge(u, v)

    print("点数:", m.node_count())
    print("边数:", m.edge_count())
    print("最大匹配条数:", m.max_matching_size())
    print("是否存在完美匹配:", m.perfect_matching_exists())
    plan = m.max_matching()
    print("一个最大匹配:", sorted(plan.items()))
    print("a 配到:", m.matched_to("a"))


def main():
    print("== 第一段：基线枚举能力 ==")
    baseline_demo()
    print("== 第二段：带花树求得的最大匹配与计数 ==")
    # TODO: 第二段演示（实现后补）
    # 实现后在这里补一段：换一张含奇环的稍大图，先跑带花树求最大匹配，
    # 打印花收缩次数与增广次数，再打印匹配条数与方案，并用同一批数据把
    # 新老两条路的结果对一遍，确认条数与方案都一致；再打印一次完美匹配
    # 判定与回溯枚举路的结果对照。


if __name__ == "__main__":
    main()
