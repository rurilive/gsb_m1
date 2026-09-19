"""渲染入口：Engine 持有模板注册表与过滤器表，Context 携带作用域链。"""

from collections import ChainMap

from templet import expr
from templet.errors import TemplateCycleError
from templet.filters import FILTERS
from templet.parser import parse

DEFAULT_MAX_INCLUDE_DEPTH = 10


class Context:
    """一次渲染的上下文：engine 引用 + 变量作用域链。

    push 生成子作用域（for 循环变量），parent 供回退。
    include_depth 记录当前渲染所处的 include 嵌套深度。
    """

    def __init__(self, engine, vars, parent=None, include_depth=0):
        self.engine = engine
        self.vars = vars
        self.parent = parent
        self.include_depth = include_depth

    def resolve(self, name):
        return self.vars.get(name, expr.UNDEFINED)

    def push(self, scope):
        return Context(self.engine, self.vars.new_child(scope), self,
                       self.include_depth)


class Engine:
    """模板引擎：register/render 管理命名模板，render_string 渲染一次性源码。"""

    def __init__(self, autoescape=True, max_include_depth=DEFAULT_MAX_INCLUDE_DEPTH):
        self.autoescape = autoescape
        self.max_include_depth = max_include_depth
        self.filters = dict(FILTERS)
        self._templates = {}

    def register(self, name, source):
        """登记命名模板，同名覆盖。"""
        self._templates[name] = source

    def render(self, name, ctx=None):
        """渲染命名模板。未注册的名字抛 KeyError。"""
        if name not in self._templates:
            raise KeyError(name)
        context = Context(self, ChainMap(dict(ctx or {})))
        out = []
        for node in parse(self._templates[name]):
            node.render(out, context)
        return "".join(out)

    def render_string(self, source, ctx=None):
        """解析并渲染一段源码，不进注册表。ctx 是变量字典。"""
        context = Context(self, ChainMap(dict(ctx or {})))
        out = []
        for node in parse(source):
            node.render(out, context)
        return "".join(out)

    def include(self, name, out, ctx):
        """IncludeNode 的展开入口。

        沿用当前上下文变量（不新建作用域），被包含模板的产物直接追加、
        不再二次转义；include 嵌套超过 max_include_depth 抛
        TemplateCycleError，未注册的名字沿用注册表的 KeyError。
        """
        depth = ctx.include_depth + 1
        if depth > self.max_include_depth:
            raise TemplateCycleError(
                "include 深度超过上限 %d（在 %r 处）" % (
                    self.max_include_depth, name))
        source = self._templates[name]
        sub_ctx = Context(self, ctx.vars, None, depth)
        for node in parse(source):
            node.render(out, sub_ctx)
