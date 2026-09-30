"""lct 现状演示。

第一段：用邻接表加深搜的朴素实现演示森林的加边、删边、连通性，
以及路径点权和与最值，看每次查询都要把整棵树重新走一遍。
第二段：预留的伸展树辅助树路径演示位子（见文末注释）。
"""

from lct import Erro, Forest


def main():
    print("=== 朴素深搜森林（现有能力） ===")
    forest = Forest(6)
    values = [7, 3, 9, 1, 5, 2]
    for node, value in enumerate(values):
        forest.set_value(node, value)
    print("  初始点权        ->", [forest.get_value(i) for i in range(6)])

    forest.link(0, 1)
    forest.link(1, 2)
    forest.link(2, 3)
    print("  link 0-1-2-3 后边数 ->", forest.edge_count)
    print("  connected(0, 3) ->", forest.connected(0, 3))
    print("  connected(4, 5) ->", forest.connected(4, 5))

    print("  path(0, 3)      ->", forest.path(0, 3))
    print("  path_sum(0, 3)  ->", forest.path_sum(0, 3))
    print("  path_min(0, 3)  ->", forest.path_min(0, 3))
    print("  path_max(0, 3)  ->", forest.path_max(0, 3))

    print("  has_edge(1, 2)  ->", forest.has_edge(1, 2))
    forest.cut(1, 2)
    print("  cut 1-2 后边数  ->", forest.edge_count)
    print("  connected(1, 3) ->", forest.connected(1, 3))

    try:
        forest.cut(1, 2)
    except Erro as error:
        print("  再次 cut 1-2    -> 报错", type(error).__name__)

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
