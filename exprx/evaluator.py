"""求值器：AST → 值。绑定表挂在求值器实例上，可跨多次 evaluate 复用。"""

from .lexer import tokenize
from .parser import Parser


class Evaluator:

    def __init__(self):
        self._env = {}

    def evaluate(self, text, variables=None):
        """求值一个表达式；variables 是本次调用的外部绑定。"""
        if variables:
            self._env.update(variables)
        ast = Parser(tokenize(text)).parse()
        return self._eval(ast)

    def _eval(self, node):
        kind = node[0]
        if kind == "num":
            return node[1]
        if kind == "name":
            if node[1] not in self._env:
                raise NameError(f"未绑定的变量: {node[1]}")
            return self._env[node[1]]
        if kind == "neg":
            return -self._eval(node[1])
        if kind == "bin":
            return self._binary(node[1], self._eval(node[2]), self._eval(node[3]))
        if kind == "cmp":
            return self._compare(node[1], self._eval(node[2]), self._eval(node[3]))
        if kind == "and":
            left = self._eval(node[1])
            right = self._eval(node[2])
            return bool(left) and bool(right)
        if kind == "or":
            left = self._eval(node[1])
            right = self._eval(node[2])
            return bool(left) or bool(right)
        if kind == "let":
            return self._eval_let(node)
        raise ValueError(f"未知节点: {kind}")

    def _eval_let(self, node):
        _, name, value_node, body = node
        self._env[name] = self._eval(value_node)
        return self._eval(body)

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
            return int(left / right)
        if op == "%":
            return left - int(left / right) * right
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
