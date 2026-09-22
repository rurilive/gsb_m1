"""全量词法扫描。

scan(text) 从文本开头一路扫到末尾，产出一串 Token 再加一个 EOF。
编辑器把每次击键翻成一次编辑，然后整段重扫一遍。

语言的形状：
  空白            空格、制表、回车，不进 token 流，但行列要跟着走；
  换行            \\n，行号加一，列回到 1；
  identifier      [A-Za-z_][A-Za-z0-9_]*
  number          \\d+ 或 \\d+.\\d+
  string          "..."，反斜杠可转义下一个字符，串里不许出现换行；
  行注释          # 到行尾，不含行尾的换行；
  块注释          /* 到 */，可以跨行；
  operator        两字符优先（== != <= >= && || ->），否则单字符；
  EOF             文本末尾补一个，text 为空串。

收不住的串、没关的块注释、认不出的字符都算 error token：
  收不住的串扫到换行或文件末尾为止，token 里不含那个换行；
  没关的块注释一路吃到文件末尾；
  认不出的字符一字一个 error，不跟相邻的凑团。
"""

import re

from lexbend.token import (
    COMMENT,
    EOF,
    ERROR,
    IDENT,
    NUMBER,
    OP,
    STRING,
    Token,
    ONE_CHAR_OPS,
    TWO_CHAR_OPS,
)

__all__ = ["Cursor", "iter_tokens", "scan"]

_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
_OP_RE = re.compile("|".join(re.escape(op) for op in TWO_CHAR_OPS)
                    + "|[" + re.escape(ONE_CHAR_OPS) + "]")

_WHITESPACE = " \t\r"


class Cursor:
    """扫描游标：pos 往前走，行列同步跟上。

    行列从 1 数，列按字符数，制表符算一格。对外暴露是为了能从
    中途起扫：给定 (pos, line, col) 接上，walk 到哪儿位置就是哪儿。
    """

    __slots__ = ("text", "pos", "line", "col")

    def __init__(self, text, pos=0, line=1, col=1):
        self.text = text
        self.pos = pos
        self.line = line
        self.col = col

    def seek(self, end):
        """把游标推到 end，路上的换行与列数一并结清。"""
        if end > self.pos:
            seg = self.text[self.pos:end]
            newlines = seg.count("\n")
            if newlines:
                self.line += newlines
                self.col = len(seg) - seg.rfind("\n")
            else:
                self.col += len(seg)
        self.pos = end

    def here(self):
        return self.pos, self.line, self.col

    def at_end(self):
        return self.pos >= len(self.text)


def _string_end(text, start):
    """从开引号处找串的收尾，返回 (end, closed)。

    反斜杠把下一个字符原样带过；撞上换行或文件末尾都算没收住。
    """
    size = len(text)
    i = start + 1
    while i < size:
        ch = text[i]
        if ch == "\\":
            i += 2
        elif ch == "\n":
            return i, False
        elif ch == '"':
            return i + 1, True
        else:
            i += 1
    return size, False


def iter_tokens(text):
    """逐 token 产出，末尾跟一个 EOF（空文本只出 EOF）。"""
    return _scan(Cursor(text))


def _scan(cur):
    """从游标当前位置扫到尾，游标要放在某个 token 边界上。"""
    text = cur.text
    size = len(text)
    while not cur.at_end():
        start, line, col = cur.here()
        ch = text[start]

        if ch == "\n" or ch in _WHITESPACE:
            cur.seek(start + 1)
            continue

        if ch == "#":
            end = text.find("\n", start)
            if end < 0:
                end = size
            yield Token(COMMENT, text[start:end], start, end, line, col)
            cur.seek(end)
            continue

        if ch == "/" and text.startswith("/*", start):
            end = text.find("*/", start + 2)
            if end < 0:
                yield Token(ERROR, text[start:], start, size, line, col)
                cur.seek(size)
                continue
            end += 2
            yield Token(COMMENT, text[start:end], start, end, line, col)
            cur.seek(end)
            continue

        if ch == '"':
            end, closed = _string_end(text, start)
            kind = STRING if closed else ERROR
            yield Token(kind, text[start:end], start, end, line, col)
            cur.seek(end)
            continue

        match = _IDENT_RE.match(text, start)
        if match:
            end = match.end()
            yield Token(IDENT, match.group(), start, end, line, col)
            cur.seek(end)
            continue

        match = _NUMBER_RE.match(text, start)
        if match:
            end = match.end()
            yield Token(NUMBER, match.group(), start, end, line, col)
            cur.seek(end)
            continue

        match = _OP_RE.match(text, start)
        if match:
            end = match.end()
            yield Token(OP, match.group(), start, end, line, col)
            cur.seek(end)
            continue

        yield Token(ERROR, ch, start, start + 1, line, col)
        cur.seek(start + 1)

    yield Token(EOF, "", size, size, cur.line, cur.col)


def scan(text):
    """全量扫描的入口，返回 token 列表，最后一个恒为 EOF。"""
    return list(iter_tokens(text))
