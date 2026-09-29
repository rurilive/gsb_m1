"""递归下降解析器：把数学表达式编成语法树。

文法（由低到高，全部左结合）：
    expr    := term (('+' | '-') term)*
    term    := unary (('*' | '/' | '%') unary)*
    unary   := ('+' | '-') unary | primary
    primary := NUMBER | NAME | '(' expr ')'

词法层已经能识别比较、逻辑与赋值运算符，但文法尚未接入，遇到它们会在解析期
被当作多余内容拦下。比较、逻辑、赋值的接入留待后续在此基础上扩展。
"""

from .ast import Binary, Number, Unary, Variable
from .errors import ParseError, error_at
from .lexer import tokenize


class Parser:
    """消费 token 序列，产出语法树。

    src 只用于把报错位置换算回原文。
    """

    def __init__(self, tokens, src):
        self.tokens = tokens
        self.src = src
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos]

    def advance(self):
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def expect(self, kind, what):
        tok = self.peek()
        if tok.kind != kind:
            raise error_at(ParseError, "这里应当是%s" % what, self.src, tok)
        return self.advance()

    def parse_expr(self):
        node = self.parse_term()
        while self.peek().kind == "OP" and self.peek().text in ("+", "-"):
            op = self.advance()
            right = self.parse_term()
            node = Binary(op, op.text, node, right)
        return node

    def parse_term(self):
        node = self.parse_unary()
        while self.peek().kind == "OP" and self.peek().text in ("*", "/", "%"):
            op = self.advance()
            right = self.parse_unary()
            node = Binary(op, op.text, node, right)
        return node

    def parse_unary(self):
        tok = self.peek()
        if tok.kind == "OP" and tok.text in ("+", "-"):
            self.advance()
            operand = self.parse_unary()
            return Unary(tok, tok.text, operand)
        return self.parse_primary()

    def parse_primary(self):
        tok = self.peek()
        if tok.kind == "NUMBER":
            self.advance()
            return Number(tok, tok.value)
        if tok.kind == "NAME":
            self.advance()
            return Variable(tok, tok.text)
        if tok.kind == "LPAREN":
            self.advance()
            node = self.parse_expr()
            self.expect("RPAREN", "右括号")
            return node
        raise error_at(ParseError, "这里应当是一个表达式", self.src, tok)


def parse(src):
    """把表达式字符串解析成语法树，末尾残留 token 一律报错。

    非标准形式（如 1 + 2 3、1 2、1 == 2）在这里被拦下，须显式加括号。
    """
    tokens = tokenize(src)
    parser = Parser(tokens, src)
    node = parser.parse_expr()
    tail = parser.peek()
    if tail.kind != "END":
        raise error_at(ParseError, "表达式后面还有多余的内容", src, tail)
    return node