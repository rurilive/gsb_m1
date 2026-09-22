"""词法单元。

Token 是扫描的唯一输出物：种类、原文、半开区间 [start, end)、
以及词头所在的行列。行、列都从 1 数起。
"""

IDENT = "IDENT"
NUMBER = "NUMBER"
STRING = "STRING"
OP = "OP"
COMMENT = "COMMENT"
ERROR = "ERROR"
EOF = "EOF"

KINDS = (IDENT, NUMBER, STRING, OP, COMMENT, ERROR, EOF)

# 运算符表，最长匹配优先：先试两个字符的，再退到一个字符。
TWO_CHAR_OPS = ("==", "!=", "<=", ">=", "&&", "||", "->")
ONE_CHAR_OPS = "+-*/%=<>!&|()[]{},;.:"


class Token:
    """一个词法单元。字段都是普通属性，比较一律走 key()。"""

    __slots__ = ("kind", "text", "start", "end", "line", "col")

    def __init__(self, kind, text, start, end, line, col):
        self.kind = kind
        self.text = text
        self.start = start
        self.end = end
        self.line = line
        self.col = col

    def key(self):
        """稳定视图：(种类, 原文, 起, 止, 行, 列)。"""
        return (self.kind, self.text, self.start, self.end, self.line, self.col)

    def __repr__(self):
        return "Token(%s, %r, %d, %d, %d, %d)" % self.key()


def keys(tokens):
    """一串 token 的比较视图，对拍拿它当基准。"""
    return [t.key() for t in tokens]
