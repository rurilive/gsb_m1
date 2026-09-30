"""hldx 现状演示。

第一段：搭一棵小树，用逐节点遍历看深度、最近公共祖先、路径和、路径最值
与子树和，再演示一次路径加与子树加；
第二段：预留的重链剖分演示位子（见文末注释）。
"""

from hldx.tree import PathTree


def main():
    print("=== 逐节点遍历 ===")
    #        1
    #       / \
    #      2   3
    #     / \   \
    #    4   5   6
    tree = PathTree(1, [(1, 2), (1, 3), (2, 4), (2, 5), (3, 6)])
    for node, value in {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6}.items():
        tree.set_weight(node, value)

    print("  根 %d，节点 %s" % (tree.root, tree.nodes()))
    print("  节点 4 的深度 %d" % tree.depth(4))
    print("  4 与 6 的最近公共祖先 %d" % tree.lca(4, 6))
    print("  4 到 6 的路径 %s" % tree.path_nodes(4, 6))
    print("  4 到 6 的路径和 %d" % tree.path_sum(4, 6))
    print("  4 到 6 的路径最大值 %d" % tree.path_max(4, 6))
    print("  以 2 为根的子树和 %d" % tree.subtree_sum(2))

    print("  4 到 6 路径加 1，受影响节点 %s" % tree.update(4, 6, 1))
    print("  加完后 4 到 6 的路径和 %d" % tree.path_sum(4, 6))
    print("  以 2 为根的子树加 3，受影响节点 %s" % tree.add_subtree(2, 3))
    print("  加完后以 2 为根的子树和 %d" % tree.subtree_sum(2))

    # TODO: 第二段演示（实现后补）
    # 重链剖分实现后，在这里加一段演示：先打印重链条数、最长链长度与每条链的
    # 下标区间，确认每条链在映射数组里连续；再补一轮路径和、路径最值、子树加
    # 与最近公共祖先，用同一批数据把剖分结果与逐节点遍历的结果对一遍，确认
    # 两边一致。


if __name__ == "__main__":
    main()
