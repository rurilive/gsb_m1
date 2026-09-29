"""dsulib 现状演示。

第一段：加入若干元素，做几次合并，查看连通判定、分量大小与计数。
第二段：预留的迭代演示位子（见文末注释）。
"""

from dsulib.union import Recompute


def main():
    print("=== 朴素连通集合（现有能力） ===")
    d = Recompute()
    for x in ["a", "b", "c", "d", "e"]:
        d.add(x)
    print(f"  初始分量数       -> {d.count_components()}")
    d.union("a", "b")
    d.union("b", "c")
    d.union("d", "e")
    print(f"  connected(a, c)  -> {d.connected('a', 'c')}")
    print(f"  connected(a, d)  -> {d.connected('a', 'd')}")
    print(f"  component_size(a)-> {d.component_size('a')}")
    print(f"  members(a)       -> {sorted(d.members('a'))}")
    print(f"  合并后分量数     -> {d.count_components()}")

    # TODO: 第二段演示（实现后补）
    # 并入查集改造完成后，在这里补一轮合并、带权求差与回滚演示：
    # 建一条带相对权重的链，打印两元素的带权差值；
    # 再做若干次 union 后逐次回滚，展示集合结构与计数都回到对应时刻。


if __name__ == "__main__":
    main()
