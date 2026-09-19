"""递归下降语法分析：token 序列 → AST（元组表示）。

AST 节点：
    ("num", value) ("name", id) ("neg", e)
    ("bin", op, left, right) ("cmp", op, left, right)
    ("and", left, right) ("or", left, right)
    ("let", name, value, body)
"""

from .lexer import tokenize

_COMPARISONS = {"==", "!=", "<", "<=", ">", ">="}


class Parser:
    """优先级从低到高：or < and < 比较 < 加减 < 乘除 < 乘方 < 原子。"""

    def __init__(self, tokens):
        self._tokens = tokens
        self._pos = 0

    def parse(self):
        node = self._or()
        tok = self._peek()
        if tok.kind != "eof":
            raise SyntaxError(f"表达式末尾有多余内容: {tok.value!r}")
        return node

    # ---- 每层只消费属于自己优先级的运算符 ----

    def _or(self):
        node = self._and()
        while self._match_keyword("or"):
            node = ("or", node, self._and())
        return node

    def _and(self):
        node = self._cmp()
        while self._match_keyword("and"):
            node = ("and", node, self._cmp())
        return node

    def _cmp(self):
        node = self._add()
        tok = self._peek()
        if tok.kind == "op" and tok.value in _COMPARISONS:
            self._advance()
            node = ("cmp", tok.value, node, self._add())
        return node

    def _add(self):
        node = self._mul()
        while True:
            tok = self._peek()
            if tok.kind == "op" and tok.value in ("+", "-"):
                self._advance()
                node = ("bin", tok.value, node, self._mul())
            else:
                return node

    def _mul(self):
        node = self._power()
        while True:
            tok = self._peek()
            if tok.kind == "op" and tok.value in ("*", "/", "//", "%"):
                self._advance()
                node = ("bin", tok.value, node, self._power())
            else:
                return node

    def _power(self):
        base = self._atom()
        if self._match("^"):
            # 乘方右结合：2^3^2 等价 2^(3^2)
            return ("bin", "^", base, self._power())
        return base

    def _atom(self):
        tok = self._peek()
        if tok.kind == "number":
            self._advance()
            return ("num", tok.value)
        if tok.kind == "name":
            self._advance()
            return ("name", tok.value)
        if tok.kind == "op" and tok.value == "(":
            self._advance()
            node = self._or()
            self._expect(")")
            return node
        if tok.kind == "op" and tok.value == "-":
            self._advance()
            return ("neg", self._atom())
        if tok.kind == "keyword" and tok.value == "let":
            self._advance()
            name_tok = self._peek()
            if name_tok.kind != "name":
                raise SyntaxError("let 后面应是变量名")
            self._advance()
            self._expect("=")
            value = self._or()
            self._expect_keyword("in")
            body = self._or()
            return ("let", name_tok.value, value, body)
        raise SyntaxError(f"意外的符号: {tok.value!r}")

    # ---- 游标工具 ----

    def _peek(self):
        return self._tokens[self._pos]

    def _advance(self):
        tok = self._tokens[self._pos]
        if tok.kind != "eof":
            self._pos += 1
        return tok

    def _match(self, op_value):
        tok = self._peek()
        if tok.kind == "op" and tok.value == op_value:
            self._advance()
            return True
        return False

    def _match_keyword(self, word):
        tok = self._peek()
        if tok.kind == "keyword" and tok.value == word:
            self._advance()
            return True
        return False

    def _expect(self, op_value):
        if not self._match(op_value):
            raise SyntaxError(f"应有 {op_value!r}，实际是 {self._peek().value!r}")

    def _expect_keyword(self, word):
        if not self._match_keyword(word):
            raise SyntaxError(f"应有关键字 {word!r}，实际是 {self._peek().value!r}")


def parse(text):
    return Parser(tokenize(text)).parse()
