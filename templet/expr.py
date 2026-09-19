"""表达式子语言：递归下降解析 + 求值。

支持字面量（数字/字符串/True/False/None）、名字、点属性、下标、
比较（== != < > <= >= in / not in）、and/or/not（短路，返回操作数值）。
缺失的名字、属性或键求值为 UNDEFINED：渲染为空串、为假、比较得 False。
"""

import re

from templet.errors import TemplateSyntaxError

_NUM_RE = re.compile(r"\d+(?:\.\d+)?")
_STR_RE = re.compile(r"""["']([^"']*)["']""")
_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_CONSTS = {"True": True, "False": False, "None": None}


class Undefined:
    """缺失值的占位（单例）：为假、渲染空串。"""

    _inst = None

    def __new__(cls):
        if cls._inst is None:
            cls._inst = super().__new__(cls)
        return cls._inst

    def __bool__(self):
        return False

    def __str__(self):
        return ""

    def __repr__(self):
        return "Undefined"


UNDEFINED = Undefined()


def is_undefined(value):
    return isinstance(value, Undefined)


def parse(text):
    """表达式文本 -> AST 元组；语法错误抛 TemplateSyntaxError。"""
    tokens = _lex(text)
    if not tokens:
        raise TemplateSyntaxError("空表达式")
    node, pos = _parse_binary(tokens, 0, 0)
    if pos != len(tokens):
        raise TemplateSyntaxError("表达式有多余内容: %r" % text)
    return node


def evaluate(node, resolve):
    """对 AST 求值。resolve(name) 提供变量值。"""
    kind = node[0]
    if kind == "const":
        return node[1]
    if kind == "name":
        return resolve(node[1])
    if kind == "attr":
        return _get_attr(evaluate(node[1], resolve), node[2])
    if kind == "item":
        try:
            return evaluate(node[1], resolve)[evaluate(node[2], resolve)]
        except Exception:
            return UNDEFINED
    if kind == "not":
        return not evaluate(node[1], resolve)
    if kind == "and":
        left = evaluate(node[1], resolve)
        return evaluate(node[2], resolve) if left else left
    if kind == "or":
        left = evaluate(node[1], resolve)
        return left if left else evaluate(node[2], resolve)
    if kind == "cmp":
        return _compare(node[1], evaluate(node[2], resolve), evaluate(node[3], resolve))
    raise TemplateSyntaxError("未知节点: %r" % (kind,))


def _lex(text):
    """切 token：(kind, value)，kind in num / str / name / op。"""
    tokens, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
        elif c.isdigit():
            m = _NUM_RE.match(text, i)
            v = m.group(0)
            tokens.append(("num", float(v) if "." in v else int(v)))
            i = m.end()
        elif c in "\"'":
            m = _STR_RE.match(text, i)
            if not m:
                raise TemplateSyntaxError("字符串未闭合: %r" % text)
            tokens.append(("str", m.group(1)))
            i = m.end()
        elif c.isalpha() or c == "_":
            m = _NAME_RE.match(text, i)
            tokens.append(("name", m.group(0)))
            i = m.end()
        elif text[i:i + 2] in ("==", "!=", "<=", ">="):
            tokens.append(("op", text[i:i + 2]))
            i += 2
        elif c in "<>[].":
            tokens.append(("op", c))
            i += 1
        else:
            raise TemplateSyntaxError("表达式含非法字符 %r: %r" % (c, text))
    return tokens


# ---- 语法：优先级爬升，优先级低的先匹配 ----

_PREC = {"or": 1, "and": 2, "==": 3, "!=": 3, "<": 3,
         ">": 3, "<=": 3, ">=": 3, "in": 3, "not in": 3}


def _peek_op(toks, i):
    """i 处若是二元操作符，返回 (名称, 消耗 token 数)，否则 None。"""
    if i >= len(toks):
        return None
    kind, value = toks[i]
    if kind == "op" and value in _PREC or kind == "name" and value in ("and", "or", "in"):
        return value, 1
    if toks[i] == ("name", "not") and toks[i + 1:i + 2] == [("name", "in")]:
        return "not in", 2
    return None


def _parse_binary(toks, i, min_prec):
    left, i = _parse_unary(toks, i)
    while True:
        op = _peek_op(toks, i)
        if op is None or _PREC[op[0]] < min_prec:
            return left, i
        name, width = op
        right, i = _parse_binary(toks, i + width, _PREC[name] + 1)
        left = (name, left, right) if name in ("and", "or") else ("cmp", name, left, right)


def _parse_unary(toks, i):
    if toks[i:i + 1] == [("name", "not")]:
        node, i = _parse_unary(toks, i + 1)
        return ("not", node), i
    return _parse_atom(toks, i)


def _parse_atom(toks, i):
    if i >= len(toks):
        raise TemplateSyntaxError("表达式不完整")
    kind, value = toks[i]
    if kind in ("num", "str"):
        node, i = ("const", value), i + 1
    elif kind == "name":
        if value in ("and", "or", "not", "in"):
            raise TemplateSyntaxError("关键字不能作变量: %r" % value)
        node = ("const", _CONSTS[value]) if value in _CONSTS else ("name", value)
        i += 1
    else:
        raise TemplateSyntaxError("意外的记号 %r" % value)
    while i < len(toks):
        if toks[i] == ("op", "."):
            if i + 1 >= len(toks) or toks[i + 1][0] != "name":
                raise TemplateSyntaxError("`.` 后应为属性名")
            node, i = ("attr", node, toks[i + 1][1]), i + 2
        elif toks[i] == ("op", "["):
            sub, i = _parse_binary(toks, i + 1, 0)
            if i >= len(toks) or toks[i] != ("op", "]"):
                raise TemplateSyntaxError("下标缺少 `]`")
            node, i = ("item", node, sub), i + 1
        else:
            break
    return node, i


# ---- 求值辅助 ----

def _get_attr(obj, name):
    """属性查值：字典键优先，其次 getattr；下划线开头一律不开放。"""
    if name.startswith("_") or is_undefined(obj):
        return UNDEFINED
    if isinstance(obj, dict) and name in obj:
        return obj[name]
    try:
        return getattr(obj, name)
    except AttributeError:
        return UNDEFINED


def _compare(op, a, b):
    if is_undefined(a) or is_undefined(b):
        return False
    try:
        if op == "==":
            return a == b
        if op == "!=":
            return a != b
        if op == "<":
            return a < b
        if op == ">":
            return a > b
        if op == "<=":
            return a <= b
        if op == ">=":
            return a >= b
        if op == "in":
            return a in b
        return a not in b
    except TypeError:
        return False
