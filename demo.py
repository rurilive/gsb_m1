"""lcatree 现状演示。

第一段：搭一棵小树，用沿父指针逐级上溯的朴素实现看最近公共祖先、
两点距离与路径；
第二段：预留的倍增实现演示位子，见文末注释。
"""

from lcatree.tree import Tree


def main():
    print("=== 朴素逐级上溯 ===")
    t = Tree({10: None, 20: 10, 30: 10, 40: 20, 50: 20, 60: 30})
    print("  根 %r，结点 %s" % (t.root, t.nodes()))
    print("  40 到根的路径 %s" % (t.path_to_root(40),))
    print("  40 与 50 的最近公共祖先 %r" % (t.lca(40, 50),))
    print("  40 与 60 的最近公共祖先 %r" % (t.lca(40, 60),))
    print("  40 与 60 的距离 %d" % (t.distance(40, 60),))
    print("  40 到 60 的路径 %s" % (t.path(40, 60),))
    print("  路径按编号排序 %s" % (t.path_sorted(40, 60),))
    print("  20 在 40 到 60 的路径上 %r" % (t.on_path(20, 40, 60),))
    print("  两条路径相交 %r" % (t.paths_intersect(40, 50, 20, 60),))

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
