"""Matcher 现状演示。

第一段：逐模式滑动比较的朴素能力，展示命中位置、计数与命中总数。
第二段：预留的自动机演示位子（见文末注释）。
"""

from acx.multi import Matcher


def main():
    print("=== 朴素多模式匹配 ===")
    patterns = ["he", "she", "hers", "a"]
    text = "ushers"
    m = Matcher(patterns)
    print("  模式 = {}".format(patterns))
    print("  文本 = {!r}".format(text))
    for pattern in patterns:
        print("  find({!r}) = {}".format(pattern, m.find(pattern, text)))
    print("  count('he') = {}".format(m.count("he", text)))
    print("  total = {}".format(m.total(text)))

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
