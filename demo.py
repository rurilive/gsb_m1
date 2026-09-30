"""linbasis 现状演示。

第一段：在一小组整数上跑基线能力，看最大异或和、最小异或和、不同异或值
个数、第k小异或和、能否异或表示，以及两组数空间的合并，并把枚举过的子集
个数与异或运算次数打印出来。
第二段：预留给改造后的快速路径演示（按位维护的线性基、一趟插入与查询、
两路逐项对照与规模计数对照），见文末注释，待实现补齐。
"""

from linbasis.core import XorSpace


def demo_baseline():
    print("== 基线：异或空间 ==")
    xs = XorSpace([3, 5, 6])
    print("元素 =", xs.numbers)

    print("最大异或和 =", xs.max_xor())
    print("枚举子集数 =", xs.subset_count)
    print("异或运算数 =", xs.xor_steps)

    print("最小异或和 =", xs.min_xor())
    print("不同异或值个数 =", xs.xor_space_size())
    print("第零小异或和 =", xs.kth_xor(0))
    print("第三小异或和 =", xs.kth_xor(3))
    print("能否表示六 =", xs.can_represent(6))
    print("能否表示四 =", xs.can_represent(4))

    print("== 基线：合并两组数的异或空间 ==")
    merged = xs.merge_spaces([12])
    print("合并后元素 =", merged.numbers)
    print("合并后最大异或和 =", merged.max_xor())
    print("合并后不同异或值个数 =", merged.xor_space_size())

    print("== 基线：边界 ==")
    empty = XorSpace([])
    print("空集合最大异或和 =", empty.max_xor())
    print("空集合不同异或值个数 =", empty.xor_space_size())
    zeros = XorSpace([0, 0, 0])
    print("全零最小异或和 =", zeros.min_xor())
    print("全零能否表示零 =", zeros.can_represent(0))


def demo_optimized():
    # TODO: 第二段演示（实现后补）
    pass


def main():
    demo_baseline()
    demo_optimized()


if __name__ == "__main__":
    main()
