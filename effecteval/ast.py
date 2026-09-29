"""表达式语法树节点。

解析器产出这些节点，求值器可以按 isinstance 分派，也可以走节点自带的 eval。
节点都带 token，出错时可直接定位到源上的下标。
"""


class Node:
    """语法树节点基类。"""

    __slots__ = ("token",)

    def __init__(self, token):
        self.token = token

    def eval(self, env):
        """便捷入口：转交求值器（延迟 import 以避免模块循环依赖）。"""
        from .eval import evaluate_node
        return evaluate_node(self, env)


class Number(Node):
    """字面量，值在 value 里，int 或 float。"""

    __slots__ = ("value",)

    def __init__(self, token, value):
        super().__init__(token)
        self.value = value


class Variable(Node):
    """变量引用，名字在 name 里。"""

    __slots__ = ("name",)

    def __init__(self, token, name):
        super().__init__(token)
        self.name = name


class Unary(Node):
    """一元运算，op 取 - 或 +，operand 是子节点。"""

    __slots__ = ("op", "operand")

    def __init__(self, token, op, operand):
        super().__init__(token)
        self.op = op
        self.operand = operand


class Binary(Node):
    """二元运算，op 是运算符串，left 与 right 是子节点。"""

    __slots__ = ("op", "left", "right")

    def __init__(self, token, op, left, right):
        super().__init__(token)
        self.op = op
        self.left = left
        self.right = right