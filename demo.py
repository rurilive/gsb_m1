"""reroot 现状演示。

第一段：朴素统计——对每个结点单独当根重走整棵树，逐点求子树大小、
到其它所有点的距离之和与最远步数，并给出访问次数的规模度量。
第二段：预留的两趟换根动态规划与独立对照演示位子（见文末注释）。
"""

from reroot import Reroot, RerootError


def build_sample():
    """一段样例：根 0，链 0 到 1 到 2 到 3，2 号上再挂叶子 4 与 5。"""
    tree = Reroot()
    tree.load(6, [(0, 1), (1, 2), (2, 3), (2, 4), (2, 5)])
    return tree


def main():
    tree = build_sample()
    print("=== 朴素统计（每个结点单独当根重走整棵树） ===")
    print(f"  结点 {tree.node_count()}")

    print(f"  以 0 为根的子树大小 {tree.subtree_sizes(0)}")
    print(f"  以 2 为根的子树大小 {tree.subtree_sizes(2)}")

    print(f"  各点到其它所有点的距离之和 {tree.all_distance_sums()}")
    print(f"  各点出发的最远步数 {tree.all_deepest_subtrees()}")

    print(f"  朴素口径访问结点总次数 {tree.visit_count()}")

    try:
        tree.distance_sum(99)
    except RerootError as err:
        print(f"  越界结点被统一基类拦下 {type(err).__name__}")

    # TODO: 第二段演示（实现后补）
    # 第一遍自根向下求出深度与子树大小，第二遍自上而下用父结点已换根的
    # 结果推当前结点的结果，一趟线性求出每个结点当根的子树大小、距离之和
    # 与最远步数；再另起一条独立做法对每个结点单独深搜，在固定输入上与
    # 换根路逐项对照打印；顺手打印朴素路与换根路各走了多少次遍历，
    # 给出链状树、星形树上的规模差距。


if __name__ == "__main__":
    main()
