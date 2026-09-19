"""词法分析：把表达式字符串切成 token 序列。"""

KEYWORDS = {"let", "in", "and", "or"}

_TWO_CHAR_OPS = {"==", "!=", "<=", ">=", "//"}
_ONE_CHAR_OPS = set("+-*/%^()<>=,")


class Token:
    __slots__ = ("kind", "value")

    def __init__(self, kind, value):
        self.kind = kind      # number / name / keyword / op / eof
        self.value = value

    def __repr__(self):
        return f"Token({self.kind}, {self.value!r})"


def tokenize(text):
    tokens = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if ch.isdigit() or (ch == "." and i + 1 < n and text[i + 1].isdigit()):
            j = i
            seen_dot = False
            while j < n and (text[j].isdigit() or (text[j] == "." and not seen_dot)):
                if text[j] == ".":
                    seen_dot = True
                j += 1
            literal = text[i:j]
            tokens.append(Token("number", float(literal) if seen_dot else int(literal)))
            i = j
            continue
        if ch.isalpha() or ch == "_":
            j = i
            while j < n and (text[j].isalnum() or text[j] == "_"):
                j += 1
            word = text[i:j]
            tokens.append(Token("keyword" if word in KEYWORDS else "name", word))
            i = j
            continue
        two = text[i:i + 2]
        if two in _TWO_CHAR_OPS:
            tokens.append(Token("op", two))
            i += 2
            continue
        if ch in _ONE_CHAR_OPS:
            tokens.append(Token("op", ch))
            i += 1
            continue
        raise SyntaxError(f"无法识别的字符 {ch!r}（位置 {i}）")
    tokens.append(Token("eof", None))
    return tokens
