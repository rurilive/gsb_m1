"""布尔查询：表达式节点、求值入口、参考引擎。

表达式节点是 Tag / And / Or / Not / Diff，evaluate(node, engine) 交给
引擎做集合运算，最后输出升序的记录 id 列表。SetEngine 是参考实现，
直接拿 TagStore 里的 set 倒排表现算，语义以它为准。

引擎协议（新引擎照这个实现就能接进 evaluate）：

    postings(label)             该标签的集合，未知标签给空集合
    universe()                  全部记录 id 的集合
    intersection(a, b)          交集
    union(a, b)                 并集
    difference(a, b)            差集
    complement(a)               相对全集求补
    size(posting)               元素个数
    materialize(posting)        产出升序记录 id 列表
    stats()                     计数信息
"""


class Query:
    """表达式节点基类。"""

    _fields = ()

    def __eq__(self, other):
        return type(self) is type(other) and all(
            getattr(self, name) == getattr(other, name) for name in self._fields
        )

    def __hash__(self):
        return hash((type(self).__name__,) + tuple(
            getattr(self, name) for name in self._fields))

    def __repr__(self):
        inner = ", ".join(repr(getattr(self, name)) for name in self._fields)
        return "%s(%s)" % (type(self).__name__, inner)


class Tag(Query):
    """命中带该标签的记录。"""

    _fields = ("label",)

    def __init__(self, label):
        self.label = label


class And(Query):
    """子表达式全部命中才算。"""

    _fields = ("children",)

    def __init__(self, *children):
        self.children = tuple(children)


class Or(Query):
    """任一子表达式命中就算。"""

    _fields = ("children",)

    def __init__(self, *children):
        self.children = tuple(children)


class Not(Query):
    """取补，全集是库里全部记录。"""

    _fields = ("child",)

    def __init__(self, child):
        self.child = child


class Diff(Query):
    """左有右无。"""

    _fields = ("left", "right")

    def __init__(self, left, right):
        self.left = left
        self.right = right


def evaluate(node, engine):
    """求值，返回升序的记录 id 列表。"""
    return engine.materialize(eval_posting(node, engine))


def eval_posting(node, engine):
    """求值，返回引擎自己的集合表示。"""
    if isinstance(node, Tag):
        return engine.postings(node.label)
    if isinstance(node, Not):
        return engine.complement(eval_posting(node.child, engine))
    if isinstance(node, Diff):
        left = eval_posting(node.left, engine)
        right = eval_posting(node.right, engine)
        return engine.difference(left, right)
    if isinstance(node, And):
        parts = [eval_posting(child, engine) for child in node.children]
        acc = parts[0]
        for part in parts[1:]:
            acc = engine.intersection(acc, part)
        return acc
    if isinstance(node, Or):
        parts = [eval_posting(child, engine) for child in node.children]
        acc = parts[0]
        for part in parts[1:]:
            acc = engine.union(acc, part)
        return acc
    raise TypeError("不认识的表达式节点: %r" % (node,))


class SetEngine:
    """参考引擎：倒排集合直接用 Python set 现算。"""

    name = "set"

    def __init__(self, store):
        self._store = store
        self._ops = 0
        self._queries = 0

    def postings(self, label):
        return self._store.postings(label)

    def universe(self):
        return set(self._store.ids())

    def intersection(self, left, right):
        self._ops += 1
        return left & right

    def union(self, left, right):
        self._ops += 1
        return left | right

    def difference(self, left, right):
        self._ops += 1
        return left - right

    def complement(self, posting):
        self._ops += 1
        return set(self._store.ids()) - posting

    def size(self, posting):
        return len(posting)

    def materialize(self, posting):
        self._queries += 1
        return sorted(posting)

    def stats(self):
        return {"engine": self.name, "ops": self._ops, "queries": self._queries}


def parse(text):
    """把 "3 & (7 | ~5)" 这样的表达式解析成节点树。

    优先级从高到低：~、&、| 与 -（同级，左结合）。
    """
    tokens = _tokenize(text)
    pos = [0]

    def peek():
        return tokens[pos[0]] if pos[0] < len(tokens) else None

    def take():
        token = peek()
        pos[0] += 1
        return token

    def expr():
        node = term()
        while peek() in ("|", "-"):
            operator = take()
            right = term()
            node = Or(node, right) if operator == "|" else Diff(node, right)
        return node

    def term():
        node = factor()
        while peek() == "&":
            take()
            node = And(node, factor())
        return node

    def factor():
        token = peek()
        if token == "~":
            take()
            return Not(factor())
        if token == "(":
            take()
            node = expr()
            if take() != ")":
                raise ValueError("括号没配平")
            return node
        if isinstance(token, int):
            take()
            return Tag(token)
        raise ValueError("表达式里有看不懂的记号: %r" % (token,))

    node = expr()
    if pos[0] != len(tokens):
        raise ValueError("表达式末尾多出记号: %r" % (peek(),))
    return node


def _tokenize(text):
    tokens = []
    index = 0
    while index < len(text):
        char = text[index]
        if char.isspace():
            index += 1
        elif char.isdigit():
            end = index
            while end < len(text) and text[end].isdigit():
                end += 1
            tokens.append(int(text[index:end]))
            index = end
        elif char in "&|~()-":
            tokens.append(char)
            index += 1
        else:
            raise ValueError("表达式里有看不懂的字符: %r" % (char,))
    return tokens
