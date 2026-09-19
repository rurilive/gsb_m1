"""内置过滤器。VarNode 经 ctx.engine.filters 查用，Engine 可增删覆盖。"""

import html

from templet import expr


def f_escape(value):
    """HTML 转义（含引号）。"""
    return html.escape(str(value), quote=True)


def f_safe(value):
    """跳过转义：过滤链任意位置出现 safe 即不转义，本身原样返回。"""
    return value


def f_upper(value):
    return str(value).upper()


def f_length(value):
    """求长度；不可求长度（含 Undefined）返回 0。"""
    try:
        return len(value)
    except TypeError:
        return 0


def f_join(value, sep=", "):
    """拼接可迭代对象；Undefined 拼为空串。"""
    if expr.is_undefined(value):
        return ""
    return sep.join(str(item) for item in value)


def f_default(value, arg=""):
    """值为 Undefined 或空串时取 arg，否则原值。"""
    if expr.is_undefined(value) or value == "":
        return arg
    return value


FILTERS = {
    "escape": f_escape,
    "safe": f_safe,
    "upper": f_upper,
    "length": f_length,
    "join": f_join,
    "default": f_default,
}
