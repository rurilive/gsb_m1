"""regexlab 当前实现：只做字面量相等判断的最朴素匹配器。

一个正经的正则引擎应当先把模式解析成语法树，再把语法树编译成
自动机，最后以状态集合模拟逐字符推进文本。本文件目前只是一个
占位实现：把模式本身当作要匹配的整段文本，两边完全相等才算命中，
点号、星号、方括号、圆括号、竖线这些语法符号一概不认识，也没有
任何字符类、量词、选择、锚点、分组或回溯引用。
"""


class LiteralMatch:
    """最朴素的匹配器：判断一个模式串是否等于输入串。"""

    def __init__(self, pattern):
        self.pattern = pattern

    def test(self, text):
        """整段相等就返回 True，否则 False。"""
        return text == self.pattern

    def span(self, text):
        """整段相等返回 (0, len(text))，否则返回 None。"""
        if self.test(text):
            return (0, len(text))
        return None


def match(pattern, text):
    """从开头匹配。当前实现只要求整个文本等于模式。

    命中返回 (start, end)，失败返回 None。
    """
    return LiteralMatch(pattern).span(text)
