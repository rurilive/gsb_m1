"""基础集合现状演示。

第一段：本地增删查，加入几个元素、删掉一个、判断成员。
第二段：预留的副本合并与最终一致演示位子（见文末注释）。
"""

from orset.set import ORSet


def main():
    print("=== 本地增删查 ===")
    s = ORSet()
    s.add("apple").add("banana").add("cherry")
    print(f"  加入三个元素后 -> {sorted(s.elements())}")

    s.remove("banana")
    print(f"  删掉 banana 后 -> {sorted(s.elements())}")

    print(f"  contains('apple') -> {s.contains('apple')}")
    print(f"  contains('banana') -> {s.contains('banana')}")

    snap = s.elements()
    snap.add("dragon")
    print(f"  改动副本后原集合仍为 -> {sorted(s.elements())}")

    # TODO(副本合并与最终一致): 观察移除集、带 tag 的 add、按标签的 remove、
    # 幂等交换的 merge、因果就绪判断、混合 LWW 元素寄存器、并发下最终一致
    # 实现后，在这里加一段演示：
    # 造两个副本各自 add 与 remove，其中一方删除是在另一方并发新增之前观察到的，
    # 把两边状态互相 merge 两遍看结果幂等且与顺序无关，再检查新加的元素没有被误删，
    # 最后把两边收敛到相同状态，验证并发操作下两个副本最终一致。


if __name__ == "__main__":
    main()