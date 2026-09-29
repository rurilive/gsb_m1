"""lcalib 现状演示。

第一段：用父子边建一棵树，逐个求父节点、深度、最近公共祖先、
距离与祖先关系。
第二段：预留的迭代演示位子（见文末注释）。
"""

from lcalib.lca import NaiveLca


def main():
    print("=== 朴素最近公共祖先（现有能力） ===")
    edges = [
        ("r", "a"),
        ("r", "b"),
        ("a", "c"),
        ("a", "d"),
        ("b", "e"),
        ("e", "f"),
    ]
    tree = NaiveLca(edges)
    print(f"  树根             -> {tree.root}")
    print(f"  节点数           -> {len(tree)}")
    print(f"  a 的孩子         -> {tree.children('a')}")
    print(f"  f 的父节点       -> {tree.parent('f')}")
    print(f"  f 的深度         -> {tree.depth('f')}")

    pairs = [("c", "d"), ("c", "f"), ("f", "r"), ("b", "b")]
    for u, v in pairs:
        print(
            f"  最近公共祖先({u}, {v}) -> {tree.lca(u, v)}"
            f"   距离 -> {tree.dist(u, v)}"
            f"   祖先? -> {tree.is_ancestor(u, v)}"
        )

    batch = [("c", "e"), ("a", "f"), ("b", "e")]
    print(f"  批量最近公共祖先 -> {tree.query_many(batch)}")

    # TODO: 第二段演示（实现后补）
    # 倍增与欧拉序改造完成后，在这里补一轮演示：
    # 对同一棵树用倍增法与欧拉序稀疏表各求一遍最近公共祖先与路径边权极值，
    # 并与上面的逐层上爬结果并排打印，展示三条路口径一致。


if __name__ == "__main__":
    main()
