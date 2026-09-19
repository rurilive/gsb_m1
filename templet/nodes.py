"""节点树：每类节点实现 render(out, ctx)，把渲染结果追加进 out 列表。"""

from templet import expr
from templet.errors import TemplateError, TemplateSyntaxError


class Node:
    """节点基类。"""

    def render(self, out, ctx):
        raise NotImplementedError


class TextNode(Node):
    """静态文本，原样输出。"""

    def __init__(self, text):
        self.text = text

    def render(self, out, ctx):
        out.append(self.text)


class VarNode(Node):
    """{{ 表达式 | 过滤器 }}：求值 -> 过滤 -> 按需转义。"""

    def __init__(self, expr_text, filters):
        self.expr_text = expr_text
        self.node = expr.parse(expr_text)
        self.filters = filters  # [(名称, 参数或 None), ...]

    def render(self, out, ctx):
        value = expr.evaluate(self.node, ctx.resolve)
        for name, arg in self.filters:
            fn = ctx.engine.filters.get(name)
            if fn is None:
                raise TemplateError("未知过滤器: %r" % name)
            value = fn(value) if arg is None else fn(value, arg)
        if ctx.engine.autoescape and not any(n == "safe" for n, _ in self.filters):
            value = ctx.engine.filters["escape"](value)
        out.append(str(value))


class ForNode(Node):
    """{% for x in 表达式 %}...{% endfor %}，支持 x, y 元组解包。

    每轮迭代压入一层子作用域，循环变量在 endfor 后不可见。
    迭代对象缺失（Undefined）时整块不输出；字典按 Python 语义迭代键。
    """

    def __init__(self, targets, iter_text, body):
        self.targets = targets
        self.iter_node = expr.parse(iter_text)
        self.body = body

    def render(self, out, ctx):
        seq = expr.evaluate(self.iter_node, ctx.resolve)
        if expr.is_undefined(seq):
            return
        for item in seq:
            ctx = ctx.push(self._bind(item))
            for child in self.body:
                child.render(out, ctx)
            ctx = ctx.parent

    def _bind(self, item):
        if len(self.targets) == 1:
            return {self.targets[0]: item}
        try:
            packed = tuple(item)
        except TypeError:
            raise TemplateError("无法解包迭代元素: %r" % (item,))
        if len(packed) != len(self.targets):
            raise TemplateError(
                "解包长度不匹配: %d 个变量对 %d 个元素" % (len(self.targets), len(packed)))
        return dict(zip(self.targets, packed))


class IfNode(Node):
    """{% if 条件 %}...{% else %}...{% endif %}，条件为假走 else 分支。"""

    def __init__(self, cond_text, body, orelse):
        self.cond = expr.parse(cond_text)
        self.body = body
        self.orelse = orelse

    def render(self, out, ctx):
        branch = self.body if expr.evaluate(self.cond, ctx.resolve) else self.orelse
        for child in branch:
            child.render(out, ctx)
