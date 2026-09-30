"""NaiveStr 现状演示。

第一段跑基线功能：子串相等判定、两后缀最长公共前缀、子串出现与计数、
不同子串计数、循环同构判定，以及逐字符比较次数的如实计量。
第二段是升级路径演示的占位（见文末注释），尚未实现。
"""

from strhash import NaiveStr


def main():
    print("=== 基线功能（朴素实现） ===")
    t = NaiveStr("banana")
    print(f"  text                          = {t.text!r}")
    print(f"  substr(1, 4)                  = {t.substr(1, 4)!r}")
    print(f"  is_equal(1, 4, 3, 6)          = {t.is_equal(1, 4, 3, 6)}")
    print(f"  lcp(1, 3)                     = {t.lcp(1, 3)}")
    print(f"  contains('ana')               = {t.contains('ana')}")
    print(f"  count_pattern('ana')          = {t.count_pattern('ana')}")
    print(f"  count_distinct_substrings()   = {t.count_distinct_substrings()}")
    print(f"  is_rotation('anaban')         = {t.is_rotation('anaban')}")
    print(f"  compare_count(1, 4, 3, 6)     = {t.compare_count(1, 4, 3, 6)}")

    # TODO: 第二段演示（实现后补）
    # 多项式滚动哈希、前缀哈希与幂表实现后，在这里加一段演示：
    # 常数时间取任意子串哈希、两后缀最长公共前缀的二分求法、子串出现
    # 与循环同构的哈希判定、不同子串的哈希去重计数，以及双哈希校验与
    # 逐字符暴力对照，最后把逐字符比较次数与哈希取值次数的差距打印出来。


if __name__ == "__main__":
    main()
