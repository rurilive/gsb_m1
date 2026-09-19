"""DSL 词法分析：文本 -> Token 序列。

记号都带行号与列号（从 1 计），编译期报错靠它们定位。
行内结构：`#` 起注释（到行尾）；引号字符串不支持转义，内容原样保留。
"""

import re
from collections import namedtuple

Token = namedtuple("Token", "kind value line col")
# kind: WORD / STR / NUM / ARROW / LBRACK / RBRACK / LPAREN / RPAREN / COMMA / NL

_WORD_RE = re.compile(r"[A-Za-z_][\w./@+~-]*")
_NUM_RE = re.compile(r"-?\d+(\.\d+)?")

_PUNCT = {
    "[": "LBRACK",
    "]": "RBRACK",
    "(": "LPAREN",
    ")": "RPAREN",
    ",": "COMMA",
}


def tokenize(text):
    """把规则文本切成 Token 列表。非法字符或未闭合字符串抛 RuleCompileError。"""
    from .errors import RuleCompileError

    tokens = []
    i, line, col = 0, 1, 1
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\n":
            tokens.append(Token("NL", "\\n", line, col))
            i += 1
            line += 1
            col = 1
            continue
        if ch in " \t\r":
            i += 1
            col += 1
            continue
        if ch == "#":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if ch == '"':
            end = text.find('"', i + 1)
            if end == -1:
                raise RuleCompileError("字符串未闭合", line, col)
            tokens.append(Token("STR", text[i + 1:end], line, col))
            col += end + 1 - i
            i = end + 1
            continue
        if ch == "-" and i + 1 < n and text[i + 1] == ">":
            tokens.append(Token("ARROW", "->", line, col))
            i += 2
            col += 2
            continue
        if ch in _PUNCT:
            tokens.append(Token(_PUNCT[ch], ch, line, col))
            i += 1
            col += 1
            continue
        m = _NUM_RE.match(text, i)
        if m and (ch.isdigit() or (ch == "-" and i + 1 < n and text[i + 1].isdigit())):
            tokens.append(Token("NUM", m.group(0), line, col))
            col += m.end() - i
            i = m.end()
            continue
        m = _WORD_RE.match(text, i)
        if m:
            tokens.append(Token("WORD", m.group(0), line, col))
            col += m.end() - i
            i = m.end()
            continue
        raise RuleCompileError(f"非法字符 {ch!r}", line, col)
    return tokens
