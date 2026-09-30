"""permorder 现状演示。

第一段：在一小组元素上看朴素实现给出的下一个排列、第几个排列、名次与反查，
以及两个序列是不是互为排列。
第二段：预留的升级演示位子（见文末注释）。
"""

from permorder import PermOrder


def main():
    print("=== 排列生成与字典序（现有朴素枚举能力） ===")
    p = PermOrder()
    seq = [1, 2, 3]
    print(f"  序列 = {seq}")
    print(f"  下一个排列 = {p.next_permutation(seq)}")
    print(f"  原地改写后 = {seq}")
    print(f"  第 2 个排列（从零起算） = {p.kth_permutation([1, 2, 3], 2)}")
    print(f"  排列 [3, 2, 1] 的名次 = {p.rank([3, 2, 1])}")
    print(f"  名次 4 反查的排列 = {p.unrank([1, 2, 3], 4)}")
    print(f"  [1, 1, 2] 与 [1, 2, 1] 互为排列 = {p.is_permutation([1, 1, 2], [1, 2, 1])}")
    print(f"  含重复元素 [1, 1, 2] 的下一个排列 = {p.next_permutation([1, 1, 2])}")

    # TODO: 第二段演示（实现后补）
    # 就地构造、康托展开与序号互转实现后，在这里加一段演示：把朴素枚举路径与
    # 就地构造路径的下一个排列、第几个排列、名次与按名次反查并排打印，把含重复
    # 元素下的固定口径也打印出来，并把两边走过的排列数差距一并打印出来。


if __name__ == "__main__":
    main()
