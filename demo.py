"""radixlab 现状演示。

第一段：载入一批非负整数，看朴素实现给出的排序、按位分桶与众数。
第二段：预留的迭代演示位子（见文末注释）。
"""

from radixlab.radix import NaiveRadix


def main():
    print("=== 非比较排序（现有朴素能力） ===")
    data = [170, 45, 75, 90, 802, 24, 2, 66]
    r = NaiveRadix()
    r.load(data)
    print("  原始序列:", r.values())
    print("  十进制位宽:", r.width(), " 二进制位宽:", r.bit_width())
    print("  内置排序对照:", r.comparison_sorted())
    print("  十进制位路径:", r.lowdigit_path())
    print("  二进制位路径:", r.highdigit_path())
    print("  第 0 位众数:", r.modal_digit(0))
    print("  第 1 位分桶计数:", r.bucket_counts(1))
    print("  比较次数:", r.comparison_count(), " 分配次数:", r.placement_count())

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
