"""lcsalign 现状演示。

第一段：跑通枚举全部子序列的朴素比对，看长度与具体子序列。
第二段：预留的迭代演示位子（见文末占位注释）。
"""

from lcsalign.sequence import lcs_length, lcs_sequence, summary


def main():
    print("=== 最长公共子序列（现有能力） ===")
    a, b = "ABCBDAB", "BDCABA"
    print(f"  A = {a}")
    print(f"  B = {b}")
    print(f"  lcs_length()   -> {lcs_length(a, b)}")
    print(f"  lcs_sequence() -> {lcs_sequence(a, b)}")
    print(f"  summary()      -> {summary(a, b)}")
    print(f"  无公共元素     -> {lcs_sequence('ABC', 'XYZ')}")

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
