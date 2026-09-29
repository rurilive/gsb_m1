"""词法单元定义。

token 只记 src 上的字符下标区间 [start, end)，行列换算留给上层按需做。
"""


class Token:
    """一个词法单元。

    kind 取 NUMBER、NAME、OP、LPAREN、RPAREN、END 之一。
    text 是原始切片，start 与 end 是 src 上的半开区间 [start, end)。
    NUMBER 的 value 是解析后的 int 或 float，其余 kind 的 value 与 text 相同。
    """

    __slots__ = ("kind", "text", "value", "start", "end")

    def __init__(self, kind, text, value, start, end):
        self.kind = kind
        self.text = text
        self.value = value
        self.start = start
        self.end = end

    def is_op(self, *ops):
        """本 token 是否为给定运算符之一。"""
        return self.kind == "OP" and self.text in ops

    def is_kind(self, kind):
        return self.kind == kind

    def __repr__(self):
        return "Token(%r, %r, %d, %d)" % (self.kind, self.text, self.start, self.end)
