"""手写词法：把 JSON 文本切成记号流。

Lexer 一次认一个记号，顺带维护行列位置。
"""

import re


class JsonError(ValueError):
    """词法或语法错误。"""


WHITESPACE = " \t\n\r"

_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")
_STRING_RE = re.compile(r'"(?:[^"\\]|\\.)*"')

_PUNCT = {
    "{": "LBRACE",
    "}": "RBRACE",
    "[": "LBRACKET",
    "]": "RBRACKET",
    ",": "COMMA",
    ":": "COLON",
}

_LITERALS = {
    "true": ("TRUE", True),
    "false": ("FALSE", False),
    "null": ("NULL", None),
}

_UNESCAPE = {
    '"': '"',
    "\\": "\\",
    "/": "/",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
}


class Token:
    """一个记号：kind 是类别，value 是内容，pos/line/col 是它开头的位置。"""

    __slots__ = ("kind", "value", "pos", "line", "col")

    def __init__(self, kind, value, pos, line, col):
        self.kind = kind
        self.value = value
        self.pos = pos
        self.line = line
        self.col = col

    def __repr__(self):
        return "Token(%s, %r)" % (self.kind, self.value)


def decode_string(raw):
    """把带引号的字面量解成 Python 字符串。"""
    body = raw[1:-1]
    if "\\" not in body:
        return body
    out = []
    index = 0
    size = len(body)
    while index < size:
        ch = body[index]
        if ch != "\\":
            out.append(ch)
            index += 1
            continue
        esc = body[index + 1]
        if esc == "u":
            out.append(chr(int(body[index + 2:index + 6], 16)))
            index += 6
            continue
        mapped = _UNESCAPE.get(esc)
        if mapped is None:
            raise JsonError("非法转义 \\%s" % esc)
        out.append(mapped)
        index += 2
    return "".join(out)


class Lexer:
    """把文本切成 Token 序列。"""

    def __init__(self, text):
        self.text = text          # 还没消费的剩余文本
        self.pos = 0
        self.line = 1
        self.col = 1

    def _consume(self, count):
        chunk = self.text[:count]
        self.text = self.text[count:]
        self.pos += count
        newlines = chunk.count("\n")
        if newlines:
            self.line += newlines
            self.col = len(chunk) - chunk.rfind("\n")
        else:
            self.col += count

    def next_token(self):
        """切出下一个记号。"""
        index = 0
        text = self.text
        size = len(text)
        while index < size and text[index] in WHITESPACE:
            index += 1
        if index:
            self._consume(index)
            text = self.text
        start_pos, start_line, start_col = self.pos, self.line, self.col
        if not text:
            return Token("EOF", None, start_pos, start_line, start_col)
        ch = text[0]
        punct = _PUNCT.get(ch)
        if punct is not None:
            self._consume(1)
            return Token(punct, ch, start_pos, start_line, start_col)
        if ch == '"':
            match = _STRING_RE.match(text)
            if match is None:
                raise JsonError("字符串字面量没有闭合")
            raw = match.group(0)
            self._consume(match.end())
            return Token("STRING", decode_string(raw), start_pos, start_line, start_col)
        for word in ("true", "false", "null"):
            if text.startswith(word):
                kind, value = _LITERALS[word]
                self._consume(len(word))
                return Token(kind, value, start_pos, start_line, start_col)
        match = _NUMBER_RE.match(text)
        if match is not None:
            raw = match.group(0)
            self._consume(match.end())
            return Token("NUMBER", raw, start_pos, start_line, start_col)
        raise JsonError("无法识别的字符 %r" % (ch,))
