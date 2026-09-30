"""mpmatch 现状演示。

第一段：搭一批模式，用逐模式逐位置直接比对在文本里求出现位置与次数；
第二段：预留的字典树搭配失败指针演示位子（见文末注释）。
"""

from mpmatch.automaton import Matcher


def main():
    print("=== 朴素逐模式比对 ===")
    m = Matcher(["he", "she", "his", "hers"])
    text = "ushers"
    print("  模式 %s" % (m.patterns(),))
    print("  文本 %r" % text)
    m.reset_compare_count()
    for pattern in m.patterns():
        print("  %s -> 位置 %s 次数 %d"
              % (pattern, m.positions(pattern, text), m.count(pattern, text)))
    print("  是否存在任一命中 -> %s" % m.exists(text))
    print("  逐模式比对次数 -> %d" % m.compare_count())

    # TODO: 第二段演示（实现后补）
    #
    # 在 mpmatch 里补出字典树搭配失败指针的多模式自动机之后，在这里加一段
    # 演示：先把同一批模式装进自动机，对同一段文本只扫一趟，取回每个模式的
    # 位置与次数，与上面逐模式比对的结果逐项对照；再打印自动机的状态转移数
    # 与朴素比对次数的差距；接着打印每个位置结尾的命中模式集合；最后覆盖空
    # 模式、重复模式、前缀模式、空文本、无命中等边界，确认两种路径结论一致。


if __name__ == "__main__":
    main()
