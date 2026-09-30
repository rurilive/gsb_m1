"""mobius 现状演示。

第一段：用逐数枚举求莫比乌斯函数值、逐对求最大公约数统计互素数对与最大
公约数恰为某值的数对，并打印累计试除次数；
第二段：预留的线性筛与调和级数反演演示位子（见文末注释）。
"""

from mobius.mobius import Inversion


def main():
    print("=== 朴素逐数枚举 ===")
    inv = Inversion(30)
    inv.reset_counts()
    print("  1 到 30 的莫比乌斯函数值 -> %s" % (inv.mobius_values(),))
    for x in (1, 6, 12, 30, 49):
        print("  %d 的莫比乌斯函数值 -> %d" % (x, inv.mobius(x)))
    print("  不超过 30 的互素数对个数 -> %d" % inv.count_coprime_pairs(30))
    print("  不超过 30 且最大公约数为 1 的有序数对个数 -> %d"
          % inv.count_pairs_gcd(30, 1))
    print("  不超过 30 且最大公约数为 7 的有序数对个数 -> %d"
          % inv.count_pairs_gcd(30, 7))
    print("  一批整数中的互素下标对个数 -> %d"
          % inv.count_coprime_pairs_in([2, 3, 4, 5, 6, 7]))
    print("  累计试除次数 -> %d" % inv.trial_divisions())

    # TODO: 第二段演示（实现后补）
    #
    # 在 mobius 里补出线性筛、莫比乌斯函数表、最小质因子表与按倍数贡献的
    # 调和级数前缀累加之后，在这里加一段演示：先对同一个上界做一次线性筛，
    # 取回莫比乌斯函数表并与上面逐数枚举的结果逐项对照；再用类似埃氏筛的
    # 倍数贡献方式求出互素数对个数与最大公约数恰为某值的数对个数，与上面
    # 逐对枚举的结果逐项对照；然后打印线性筛标记次数与逐数试除次数的差距；
    # 最后覆盖上界为零或一、互素数对计数、最大公约数为一、全同、一列到某
    # 个上界、单元素等边界。


if __name__ == "__main__":
    main()
