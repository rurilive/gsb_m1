"""词法分析：把模板源码切成 text / var / tag 三类 token。"""

import re

from templet.errors import TemplateSyntaxError

_TOKEN_RE = re.compile(r"({{.*?}}|{%.*?%})", re.S)


class Token:
    """一个词法单元。kind: text | var | tag。"""

    __slots__ = ("kind", "value")

    def __init__(self, kind, value):
        self.kind = kind
        self.value = value

    def __repr__(self):
        return "Token(%s, %r)" % (self.kind, self.value)


def tokenize(source):
    """切分模板源码。语法符必须成对，残留在正文里视为未闭合。"""
    tokens = []
    pos = 0
    for m in _TOKEN_RE.finditer(source):
        if m.start() > pos:
            tokens.append(Token("text", source[pos:m.start()]))
        body = m.group(0)
        kind = "var" if body.startswith("{{") else "tag"
        tokens.append(Token(kind, body[2:-2].strip()))
        pos = m.end()
    if pos < len(source):
        tokens.append(Token("text", source[pos:]))
    for tok in tokens:
        if tok.kind == "text" and ("{{" in tok.value or "{%" in tok.value):
            raise TemplateSyntaxError("未闭合的语法符: %r" % tok.value[:40])
    return tokens
