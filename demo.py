"""SubstringStats 现状演示。

第一段：朴素枚举路径求本质不同子串个数、出现次数、最长重复子串。
第二段：预留的后缀自动机演示位子（见文末注释）。
"""

from sufauto.substat import SubstringStats


def main():
    print("=== 朴素子串统计 ===")
    s = SubstringStats("banana")
    print(f"  text            = {s.text}")
    print(f"  不同子串个数    = {s.distinct_substring_count()}")
    print(f"  ana 出现次数    = {s.count_occurrences('ana')}")
    print(f"  含 nan          = {s.contains('nan')}")
    print(f"  最长重复子串    = {s.longest_repeated_substring()}")

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
