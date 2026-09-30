"""NaiveSuffix 现状演示。

第一段跑基线功能：后缀数组排序、最长公共前缀、模式出现次数、不同子串
计数与最长重复子串。
第二段是升级路径演示的占位（见文末注释），尚未实现。
"""

from suffixarr import NaiveSuffix


def main():
    print("=== 基线功能（朴素实现） ===")
    t = NaiveSuffix("banana")
    print(f"  text                        = {t.text!r}")
    print(f"  suffix_array()              = {t.suffix_array()}")
    print(f"  lcp_of(1, 3)                = {t.lcp_of(1, 3)}")
    print(f"  count_pattern('ana')        = {t.count_pattern('ana')}")
    print(f"  count_distinct_substrings() = {t.count_distinct_substrings()}")
    print(f"  longest_repeated_substring()= {t.longest_repeated_substring()!r}")
    print(f"  compare_count()             = {t.compare_count()}")

    # TODO: 第二段演示（实现后补）
    # 线性或近线性的后缀数组构造、Kasai 逐相邻后缀最长公共前缀、由该口径
    # 支撑的模式出现次数统计与不同子串计数，以及升级前后代价的对照。


if __name__ == "__main__":
    main()
