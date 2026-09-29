"""spannex 现状演示。

第一段：在小图上判断连通。
第二段：预留的迭代演示位子（见文末注释）。
"""

from spannex.graph import BruteSpan


def main():
    print("=== 朴素连通判断（现有能力） ===")
    g = BruteSpan(["a", "b", "c", "d", "e"])
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    g.add_edge("c", "d")
    print(f"  nodes()        -> {g.nodes()}")
    print(f"  reached_from(a) -> {g.reached_from('a')}")
    print(f"  connected(a, d) -> {g.connected('a', 'd')}")
    print(f"  connected(a, e) -> {g.connected('a', 'e')}")
    print(f"  is_connected() -> {g.is_connected()}")

    # TODO(最小生成树改造): 最小生成树实现后，在这里加一段演示：
    # 给若干条边配上权重，构造最小生成树，打印被选中的边集与总权重；
    # 再换一张不连通的图演示最小生成森林，逐分量打印各自的边集与权重；
    # 有条件的话对同一张图对照最大生成树，打印两者总权重之差。


if __name__ == "__main__":
    main()
