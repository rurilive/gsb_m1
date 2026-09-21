"""模式串到节点树的解析。目前只认字面量和星号。"""

from .errors import PatternError

# 留给后续语法的元字符，现在遇到直接报错，不做字面量处理
RESERVED = ".|?+()[]^$\\"


class Node:
    """节点基类。"""

    __slots__ = ()

    def __repr__(self):
        return "%s()" % type(self).__name__


class Char(Node):
    """单个字面字符。"""

    __slots__ = ("ch",)

    def __init__(self, ch):
        self.ch = ch

    def __repr__(self):
        return "Char(%r)" % self.ch


class Star(Node):
    """子节点重复零次或多次，贪婪。"""

    __slots__ = ("child",)

    def __init__(self, child):
        self.child = child

    def __repr__(self):
        return "Star(%r)" % self.child


class Seq(Node):
    """顺序连接。"""

    __slots__ = ("children",)

    def __init__(self, children):
        self.children = tuple(children)

    def __repr__(self):
        return "Seq(%s)" % ", ".join(repr(c) for c in self.children)


def parse(pattern):
    """解析模式串，返回 Seq 节点；出错抛 PatternError。"""
    nodes = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "*":
            raise PatternError("星号前面没有可重复的内容", pattern, i)
        if ch in RESERVED:
            raise PatternError("暂不支持元字符 %r" % ch, pattern, i)
        node = Char(ch)
        i += 1
        if i < len(pattern) and pattern[i] == "*":
            node = Star(node)
            i += 1
        nodes.append(node)
    return Seq(nodes)
