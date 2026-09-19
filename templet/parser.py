"""语法分析：token 流 -> 节点树，负责 for/if/else 的块配对。"""

import re

from templet import expr
from templet.errors import TemplateSyntaxError
from templet.lexer import tokenize
from templet.nodes import ForNode, IfNode, TextNode, VarNode

_FOR_RE = re.compile(
    r"for\s+([A-Za-z_][A-Za-z0-9_]*(?:\s*,\s*[A-Za-z_][A-Za-z0-9_]*)*)\s+in\s+(.+)$",
    re.S,
)


def parse(source):
    """模板源码 -> 节点列表。"""
    tokens = tokenize(source)
    nodes, pos = _parse_block(tokens, 0, ())
    if pos != len(tokens):
        raise TemplateSyntaxError("多余的 %r" % tokens[pos].value)
    return nodes


def _parse_block(tokens, pos, stop):
    """解析到 stop 中的标签为止；返回 (节点列表, 停在的 token 下标)。"""
    nodes = []
    while pos < len(tokens):
        tok = tokens[pos]
        if tok.kind == "text":
            nodes.append(TextNode(tok.value))
            pos += 1
        elif tok.kind == "var":
            nodes.append(_parse_var(tok.value))
            pos += 1
        else:
            word = tok.value.split(None, 1)[0] if tok.value else ""
            if word in stop:
                return nodes, pos
            if word == "for":
                node, pos = _parse_for(tokens, pos)
                nodes.append(node)
            elif word == "if":
                node, pos = _parse_if(tokens, pos)
                nodes.append(node)
            else:
                raise TemplateSyntaxError("未知标签: %r" % tok.value)
    return nodes, pos


def _split_chain(text):
    """按 `|` 切过滤链，字符串字面量与括号内的 `|` 不参与切分。"""
    parts, buf, depth, quote = [], [], 0, ""
    for c in text:
        if quote:
            buf.append(c)
            if c == quote:
                quote = ""
        elif c in "\"'":
            quote = c
            buf.append(c)
        elif c == "(":
            depth += 1
            buf.append(c)
        elif c == ")":
            depth -= 1
            buf.append(c)
        elif c == "|" and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(c)
    parts.append("".join(buf).strip())
    return parts


def _parse_var(text):
    """var token 文本 -> VarNode。过滤链按 `|` 切分，参数只能是字面量。"""
    parts = _split_chain(text)
    filters = []
    for raw in parts[1:]:
        if "(" in raw:
            if not raw.endswith(")"):
                raise TemplateSyntaxError("过滤器参数括号不闭合: %r" % raw)
            name, argsrc = raw.split("(", 1)
            node = expr.parse(argsrc[:-1].strip())
            if node[0] != "const":
                raise TemplateSyntaxError("过滤器参数只能是字面量: %r" % raw)
            filters.append((name.strip(), node[1]))
        else:
            filters.append((raw, None))
    return VarNode(parts[0], filters)


def _parse_for(tokens, pos):
    m = _FOR_RE.match(tokens[pos].value)
    if not m:
        raise TemplateSyntaxError("for 标签语法: %r" % tokens[pos].value)
    targets = [t.strip() for t in m.group(1).split(",")]
    body, pos = _parse_block(tokens, pos + 1, ("endfor",))
    if pos >= len(tokens):
        raise TemplateSyntaxError("for 缺少 endfor")
    return ForNode(targets, m.group(2).strip(), body), pos + 1


def _parse_if(tokens, pos):
    cond = tokens[pos].value[len("if"):].strip()
    if not cond:
        raise TemplateSyntaxError("if 缺少条件")
    body, pos = _parse_block(tokens, pos + 1, ("endif", "else"))
    if pos >= len(tokens):
        raise TemplateSyntaxError("if 缺少 endif")
    if tokens[pos].value.split(None, 1)[0] == "else":
        if tokens[pos].value.strip() != "else":
            raise TemplateSyntaxError("else 标签不接受参数")
        orelse, pos = _parse_block(tokens, pos + 1, ("endif",))
        if pos >= len(tokens):
            raise TemplateSyntaxError("if 缺少 endif")
        return IfNode(cond, body, orelse), pos + 1
    return IfNode(cond, body, []), pos + 1
