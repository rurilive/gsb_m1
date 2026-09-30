"""bittrix 现状演示。

第一段：用逐位右移与二进制串逐字符比对演示现有各项位操作，打印访问位计数；
第二段：预留的位技巧路径与规模对照的演示位子（见文末注释）。
"""

from bittrix.naive import (
    BitTools,
    bit_position_counts,
    common_prefix_length,
    gray_adjacent_one_bit,
    is_power_of_two,
    lowest_set_bit,
    highest_set_bit,
    popcount_str,
    reverse_bits,
)


def main():
    print("=== 朴素逐位与位串比对 ===")
    value = 0b10110011
    width = 8
    print("  一的个数 %d" % popcount_str(value))
    print("  最低位一的位置 %d" % lowest_set_bit(value))
    print("  最高位一的位置 %d" % highest_set_bit(value))
    print("  是否二的幂 %s" % is_power_of_two(value))
    print("  按八位逆序 %s" % bin(reverse_bits(value, width)))
    print("  与零的公共前缀长度 %d" % common_prefix_length(value, 0, width))
    print("  与相邻整数相差一个位 %s" % gray_adjacent_one_bit(value, width))

    tools = BitTools(16)
    tools.reset_visit_count()
    big = 0xFFFF
    tools.popcount(big)
    print("  十六位全一逐位访问位次数 %d" % tools.visit_count())
    tools.reset_visit_count()
    tools.bit_position_counts([0x00FF, 0x0F0F, 0xF0F0, 0xFFFF])
    print("  批量每位置位计数 %s" % bit_position_counts(
        [0x00FF, 0x0F0F, 0xF0F0, 0xFFFF], 16))
    print("  批量求计数累计访问位次数 %d" % tools.visit_count())

    # TODO: 第二段演示（实现后补）
    #
    # 在 bittrix 里补出位技巧路径之后，在这里加一段演示：对同一批整数用位
    # 技巧路与上面的朴素路各求一遍一的个数、最低位一、最高位一、二的幂判定、
    # 按位宽逆序、两数公共前缀长度，逐项对照结果是否一致；再演示增补的相邻
    # 位差一位判定与批量每位置位计数的位技巧做法，与逐数逐位路逐项比对；最
    # 后并排打印位技巧路径访问位次数与朴素逐位循环次数，覆盖零、一、全一、
    # 二的幂、非幂、负数这类边界，确认两路结论一致。

    print("  全一的位串 %s" % bin(0xFF))


if __name__ == "__main__":
    main()
