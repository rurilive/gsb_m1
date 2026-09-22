"""递归下降解析。

子类可以替换 make_number / make_object 两个钩子，换别的数字或对象构造方式。
"""

from .lexer import JsonError, Lexer
from .numbers import Num


class Parser:
    """把记号流组装成 Python 对象。"""

    def __init__(self, text):
        self.lexer = Lexer(text)
        self._token = None

    # ---- 可替换的构造钩子 ----

    def make_number(self, raw):
        return Num(raw)

    def make_object(self, pairs):
        obj = {}
        for key, value in pairs:
            obj[key] = value
        return obj

    # ---- 记号流 ----

    def _peek(self):
        if self._token is None:
            self._token = self.lexer.next_token()
        return self._token

    def _take(self):
        token = self._peek()
        self._token = None
        return token

    def _expect(self, kind):
        token = self._take()
        if token.kind != kind:
            raise JsonError("期待 %s，读到 %s" % (kind, token.kind))
        return token

    # ---- 文法 ----

    def parse_document(self):
        value = self._parse_value()
        token = self._take()
        if token.kind != "EOF":
            raise JsonError("文档结束后还有多余内容")
        return value

    def _parse_value(self):
        token = self._peek()
        kind = token.kind
        if kind == "LBRACE":
            return self._parse_object()
        if kind == "LBRACKET":
            return self._parse_array()
        if kind == "STRING":
            self._take()
            return token.value
        if kind == "NUMBER":
            self._take()
            return self.make_number(token.value)
        if kind in ("TRUE", "FALSE", "NULL"):
            self._take()
            return token.value
        raise JsonError("不该出现的记号 %s" % (kind,))

    def _parse_object(self):
        self._expect("LBRACE")
        pairs = []
        if self._peek().kind == "RBRACE":
            self._take()
            return self.make_object(pairs)
        while True:
            key = self._expect("STRING")
            self._expect("COLON")
            pairs.append((key.value, self._parse_value()))
            token = self._take()
            if token.kind == "COMMA":
                continue
            if token.kind == "RBRACE":
                return self.make_object(pairs)
            raise JsonError("对象里出现 %s" % (token.kind,))

    def _parse_array(self):
        self._expect("LBRACKET")
        items = []
        if self._peek().kind == "RBRACKET":
            self._take()
            return items
        while True:
            items.append(self._parse_value())
            token = self._take()
            if token.kind == "COMMA":
                continue
            if token.kind == "RBRACKET":
                return items
            raise JsonError("数组里出现 %s" % (token.kind,))


def loads(text):
    """把 JSON 文本解析成 Python 对象。"""
    if isinstance(text, (bytes, bytearray)):
        text = text.decode("utf-8")
    return Parser(text).parse_document()
