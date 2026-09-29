"""分词器：把表达式字符串切成 token 序列。

数字只认十进制整数与小数，不支持科学计数法、十六进制与前后缀下划线。
标识符由字母或下划线打头，后跟字母数字下划线。
多字符运算符按最长匹配优先，例如先试 && 再试 &。

OPERATORS 里已经列出一批多字符运算符（比较、逻辑与赋值），当前文法尚未接入，
分词阶段先把它们认出来，供后续在此基础上扩展语法时直接使用。
"""

from .errors import ParseError, error_at
from .tokens import Token

# 按长度从大到小排列，保证最长匹配优先。
OPERATORS = (
    "**", "==", "!=", "<=", ">=", "&&", "||",
    "+", "-", "*", "/", "%", "<", ">", "=", "(", ")", "!", "&", "|",
)

_PUNCT_KIND = {
    "(": "LPAREN",
    ")": "RPAREN",
}

_DIGITS = "0123456789"
_IDENT_START = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_")
_IDENT_BODY = _IDENT_START | set(_DIGITS)


def _is_digit(ch):
    return ch in _DIGITS


def _match_operator(src, i):
    """在 src 的 i 处做最长匹配，命中返回运算符串，否则返回 None。"""
    for op in OPERATORS:
        if src.startswith(op, i):
            return op
    return None


def tokenize(src):
    """把 src 切成 token 列表，末尾恒有一个 END token。

    假数字、无法识别的字符都在这里报 ParseError。
    """
    tokens = []
    i = 0
    n = len(src)
    while i < n:
        ch = src[i]
        if ch in " \t\r\n":
            i += 1
            continue
        if _is_digit(ch) or (ch == "." and i + 1 < n and _is_digit(src[i + 1])):
            start = i
            seen_dot = False
            while i < n and (_is_digit(src[i]) or src[i] == "."):
                if src[i] == ".":
                    if seen_dot:
                        raise error_at(
                            ParseError, "数字里出现了第二个小数点", src,
                            Token("NUMBER", src[start:i + 1], None, start, i + 1),
                        )
                    seen_dot = True
                i += 1
            text = src[start:i]
            value = float(text) if seen_dot else int(text)
            tokens.append(Token("NUMBER", text, value, start, i))
            continue
        if ch in _IDENT_START:
            start = i
            while i < n and src[i] in _IDENT_BODY:
                i += 1
            text = src[start:i]
            tokens.append(Token("NAME", text, text, start, i))
            continue
        op = _match_operator(src, i)
        if op is None:
            raise error_at(
                ParseError, "无法识别的字符", src,
                Token("BAD", ch, ch, i, i + 1),
            )
        kind = _PUNCT_KIND.get(op, "OP")
        tokens.append(Token(kind, op, op, i, i + len(op)))
        i += len(op)
    tokens.append(Token("END", "", None, n, n))
    return tokens
