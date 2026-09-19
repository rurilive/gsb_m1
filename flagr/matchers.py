"""匹配器：对请求上下文做一次判定，并自带解释文本。

统一约定（所有字段匹配器遵守）：
- 字段在上下文中缺失 -> 判 miss（matches 返回 False），不抛异常
- 类型不符 -> 判 miss：字符串只与字符串比，布尔只与布尔比，
  数字之间 int/float 互通；比较器的上下文值必须可比较（数字）
"""

_MISSING = object()


class Matcher:
    """匹配器基类。子类实现 matches(ctx) 与 describe()。"""

    def matches(self, ctx):
        raise NotImplementedError

    def describe(self):
        raise NotImplementedError


def _fmt(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f'"{value}"'
    return repr(value)


def _typed_equal(a, b):
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    return type(a) is type(b) and a == b


class Equals(Matcher):
    """字段等于给定值。"""

    def __init__(self, field, value):
        self.field = field
        self.value = value

    def matches(self, ctx):
        v = ctx.get(self.field, _MISSING)
        return v is not _MISSING and _typed_equal(v, self.value)

    def describe(self):
        return f"{self.field} eq {_fmt(self.value)}"


class NotEquals(Matcher):
    """字段存在且不等于给定值。"""

    def __init__(self, field, value):
        self.field = field
        self.value = value

    def matches(self, ctx):
        v = ctx.get(self.field, _MISSING)
        return v is not _MISSING and not _typed_equal(v, self.value)

    def describe(self):
        return f"{self.field} ne {_fmt(self.value)}"


class InSet(Matcher):
    """字段取值在给定集合内（类型须一致）。"""

    def __init__(self, field, values):
        self.field = field
        self.values = tuple(values)

    def matches(self, ctx):
        v = ctx.get(self.field, _MISSING)
        return v is not _MISSING and any(_typed_equal(v, x) for x in self.values)

    def describe(self):
        inner = ", ".join(_fmt(x) for x in self.values)
        return f"{self.field} in [{inner}]"


class Contains(Matcher):
    """字段值（转字符串后）包含给定子串。"""

    def __init__(self, field, value):
        self.field = field
        self.value = value

    def matches(self, ctx):
        v = ctx.get(self.field, _MISSING)
        return v is not _MISSING and str(self.value) in str(v)

    def describe(self):
        return f"{self.field} contains {_fmt(self.value)}"


class Compare(Matcher):
    """数字比较：gt / ge / lt / le。上下文值不是数字判 miss。"""

    def __init__(self, op, field, value):
        self.op = op
        self.field = field
        self.value = value

    def matches(self, ctx):
        v = ctx.get(self.field, _MISSING)
        if v is _MISSING or isinstance(v, bool) or not isinstance(v, (int, float)):
            return False
        if self.op in ("gt", "ge"):
            return v > self.value if self.op == "gt" else v >= self.value
        return v < self.value if self.op == "lt" else v <= self.value

    def describe(self):
        return f"{self.field} {self.op} {_fmt(self.value)}"


class All(Matcher):
    """and 组合器：全部子条件成立。"""

    def __init__(self, children):
        self.children = tuple(children)

    def matches(self, ctx):
        return all(c.matches(ctx) for c in self.children)

    def describe(self):
        return "and(" + ", ".join(c.describe() for c in self.children) + ")"


class Any(Matcher):
    """or 组合器：任一子条件成立。"""

    def __init__(self, children):
        self.children = tuple(children)

    def matches(self, ctx):
        return any(c.matches(ctx) for c in self.children)

    def describe(self):
        return "or(" + ", ".join(c.describe() for c in self.children) + ")"
