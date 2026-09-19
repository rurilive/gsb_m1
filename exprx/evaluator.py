"""求值器：AST → 值。绑定采用作用域栈，多次 evaluate 与 let 绑定互不泄漏。"""

from .lexer import tokenize
from .parser import Parser


class Evaluator:

    def __init__(self):
        self._scopes = []

    def evaluate(self, text, variables=None):
        """求值一个表达式；variables 是本次调用的外部绑定，仅在本次求值内可见。"""
        self._scopes.append(dict(variables) if variables else {})
        try:
            ast = Parser(tokenize(text)).parse()
            return self._eval(ast)
        finally:
            self._scopes.pop()

    def _lookup(self, name):
        for scope in reversed(self._scopes):
            if name in scope:
                return scope[name]
        raise NameError(f"未绑定的变量: {name}")

    def _eval(self, node):
        kind = node[0]
        if kind == "num":
            return node[1]
        if kind == "name":
            return self._lookup(node[1])
        if kind == "neg":
            return -self._eval(node[1])
        if kind == "bin":
            return self._binary(node[1], self._eval(node[2]), self._eval(node[3]))
        if kind == "cmp":
            return self._compare(node[1], self._eval(node[2]), self._eval(node[3]))
        if kind == "and":
            # 短路：左支为假时右支不求值
            if not self._eval(node[1]):
                return False
            return bool(self._eval(node[2]))
        if kind == "or":
            # 短路：左支为真时右支不求值
            if self._eval(node[1]):
                return True
            return bool(self._eval(node[2]))
        if kind == "let":
            return self._eval_let(node)
        raise ValueError(f"未知节点: {kind}")

    def _eval_let(self, node):
        _, name, value_node, body = node
        # 绑定值在外层作用域求值，再压入仅覆盖 body 的新作用域
        value = self._eval(value_node)
        self._scopes.append({name: value})
        try:
            return self._eval(body)
        finally:
            self._scopes.pop()

    def _binary(self, op, left, right):
        if op == "+":
            return left + right
        if op == "-":
            return left - right
        if op == "*":
            return left * right
        if op == "/":
            return left / right
        if op == "//":
            # 向下取整（地板除），与 Python // 语义一致
            return left // right
        if op == "%":
            # 余数符号跟随除数：-7 % 2 == 1，与 Python % 语义一致
            return left % right
        if op == "^":
            return left ** right
        raise ValueError(f"未知运算符: {op}")

    def _compare(self, op, left, right):
        if op == "==":
            return left == right
        if op == "!=":
            return left != right
        if op == "<":
            return left < right
        if op == "<=":
            return left <= right
        if op == ">":
            return left > right
        if op == ">=":
            return left >= right
        raise ValueError(f"未知比较符: {op}")
