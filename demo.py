"""parsex 现状演示。

第一段：朴素实现——用回溯递归下降对每条文法规则逐一尝试展开，判断输入串能否
被识别，给出解析树并统计解析个数。
第二段：预留的厄尔利算法演示位子（见文末注释）。
"""

from parsex import BacktrackParser, Grammar


def describe(node, indent=0):
    """把解析树打成缩进文本。"""
    pad = "  " * indent
    if node.is_leaf():
        return f"{pad}{node.symbol}"
    lines = [f"{pad}{node.symbol}"]
    for child in node.children:
        lines.append(describe(child, indent + 1))
    return "\n".join(lines)


def main():
    print("=== 朴素回溯递归下降 ===")
    # 右递归四则表达式文法，避开基线处理不了的左递归。
    grammar = Grammar([
        ("E", "T+E"),
        ("E", "T"),
        ("T", "F*T"),
        ("T", "F"),
        ("F", "(E)"),
        ("F", "a"),
    ])
    parser = BacktrackParser(grammar)
    for text in ["a", "a+a", "(a+a)*a", "a+", ""]:
        ok = parser.accepts(text)
        print(f"  输入 {text!r} 能否识别 -> {ok}")
    print("  输入 'a+a' 的解析树：")
    print(describe(parser.parse("a+a")))

    ambiguous = Grammar([("S", "aSb"), ("S", "ab"), ("S", "")])
    amb = BacktrackParser(ambiguous)
    print(f"  歧义文法下 'aabb' 的解析个数 -> {amb.count_parses('aabb')}")
    balanced = Grammar([("S", "aSb"), ("S", "")])
    print(f"  'S' 在 'aabb' 中的匹配区间 -> "
          f"{BacktrackParser(balanced).matches('S', 'aabb')}")
    print(f"  最近一次尝试的非终结符展开次数 -> {amb.attempts()}")

    # TODO: 第二段演示（实现后补）
    # 以厄尔利算法为核心：逐位置处理条目集合，预测、扫描、完成三步推进；不做左
    # 递归改写也能处理左递归文法。实现后在这里加一段演示：用同一批文法与输入串跑
    # 厄尔利路径，打印可识别性、解析树、全部解析、区间匹配、条目数与条目重复合并
    # 次数，并与上面的回溯结果逐项对照。


if __name__ == "__main__":
    main()
