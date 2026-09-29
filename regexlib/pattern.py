"""regexlib 当前实现：只做字面匹配的最朴素模式类。

一台正经的规则匹配工具应当先把模式编译成状态与转移，再让状态机
逐字符推进文本。本文件目前只是一个占位实现：把模式串当作一整段
普通文本看待，输入与模式完全相等才算整串命中，查找子串时只是看
输入里有没有出现模式这一段。星号、问号、加号、竖线、圆括号、方
括号、点号这些符号一概不认识，一旦出现就说明调用方用错了入口，
于是立刻报错并讲清当前只支持字面匹配。

改造目标里那套以非确定有限自动机为核心的能力，本文件一件都没有。
"""

# 这些字符在当前实现里没有语法含义，出现即视为调用方误用。
_SPECIAL_CHARS = "*+?|()[].^$\\"


class RegexError(ValueError):
    """模式相关错误的基类。当前只在遇到特殊字符时抛出。"""


class LiteralPat:
    """最朴素的字面模式：只判断模式串是否作为子串出现。"""

    def __init__(self, pattern):
        if not isinstance(pattern, str):
            raise RegexError("模式必须是字符串，当前只支持字面匹配。")
        bad = sorted({ch for ch in pattern if ch in _SPECIAL_CHARS})
        if bad:
            raise RegexError(
                "当前实现只支持字面匹配，模式中不允许出现特殊字符："
                + "".join(bad)
            )
        self.pattern = pattern

    def match(self, text):
        """整串相等就返回 True，否则 False。"""
        return text == self.pattern

    def search(self, text):
        """输入里含有模式这段子串就返回 True，否则 False。"""
        return self.pattern in text

    def finditer(self, text):
        """返回模式作为子串出现的全部位置，非重叠口径。

        每个位置是一个起止二元组；空模式在每个下标处都算一次命中。
        """
        hits = []
        step = len(self.pattern) or 1
        start = 0
        while start <= len(text):
            found = text.find(self.pattern, start)
            if found < 0:
                break
            hits.append((found, found + len(self.pattern)))
            start = found + step
        return hits


def literal_match(pattern, text):
    """整串匹配入口，命中返回 True。"""
    return LiteralPat(pattern).match(text)


def literal_search(pattern, text):
    """子串查找入口，命中返回 True。"""
    return LiteralPat(pattern).search(text)
