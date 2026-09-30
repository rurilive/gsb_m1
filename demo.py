"""balancedbst 快速演示。

第一段直跑改造前的基线：往一棵普通二叉搜索树里插入、删除、查找，打印
中序序列与树高，并用有序插入暴露树退化成一条链、单次操作代价随元素个
数线性增长这一现状。
第二段预留给改造后的高效路径演示，待实现补齐。
"""

from balancedbst.tree import BalancedBST


def demo_baseline():
    print("== 基线：普通二叉搜索树，不做任何旋转 ==")
    t = BalancedBST()
    for v in (50, 30, 70, 20, 40, 60, 80):
        t.add(v)
    print("中序序列 =", t.inorder())
    print("规模 =", t.size(), " 树高 =", t.height())
    print("含 40 =", t.contains(40), " 含 41 =", t.contains(41))

    t.remove(30)
    print("删掉 30 之后中序 =", t.inorder())

    print("---- 有序插入会退化成一条链 ----")
    chain = BalancedBST()
    for v in range(1, 11):
        chain.add(v)
    print("升序插入 1..10 后 树高 =", chain.height(), " 规模 =", chain.size())
    before = chain.probes()
    chain.contains(10)
    print("查一次最深键走过的结点数 =", chain.probes() - before)


def demo_optimized():
    # TODO: 第二段演示（实现后补）
    pass


def main():
    demo_baseline()
    demo_optimized()


if __name__ == "__main__":
    main()
