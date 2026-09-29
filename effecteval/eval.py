"""表达式求值：在解析器产出的语法树上做朴素递归求值。

现有能力（基线）：

- eval(src, env=None) 每次调用都重新分词、重新解析再求值，语法树不缓存；
- 只覆盖加、减、乘、除、取模五种运算与一元正负，除法与取模的除数为零报错；
- env 是变量到数值的普通字典或 None，变量在这里查表取值，查不到报未定义变量；
- 求值过程没有任何记忆化，同一个子表达式被引用多次就重算多次；
- 不求值过程之外没有任何可观测的副作用，也没有上下文对象，全部状态都在这一函数内。

可暂停恢复、依赖跟踪、记忆化失效、副作用记录与重放、惰性短路、事务回滚与
并发隔离都留待在这个基础上补齐。
"""

from .ast import Binary, Number, Unary, Variable
from .errors import EvalError, EvalRuntimeError, error_at
from .parser import parse


def evaluate_node(node, env):
    """按节点类型分派求值。env 是变量到数值的字典或 None。"""
    if isinstance(node, Number):
        return node.value
    if isinstance(node, Variable):
        if env is None or node.name not in env:
            raise error_at(
                EvalRuntimeError, "未定义的变量 %s" % node.name, "", node.token,
            )
        return env[node.name]
    if isinstance(node, Unary):
        value = evaluate_node(node.operand, env)
        if node.op == "-":
            return -value
        if node.op == "+":
            return value
        raise error_at(
            EvalRuntimeError, "不支持的一元运算符 %s" % node.op, "", node.token,
        )
    if isinstance(node, Binary):
        return _eval_binary(node, env)
    raise EvalRuntimeError("未知的语法树节点 %r" % (node,))


def _eval_binary(node, env):
    left = evaluate_node(node.left, env)
    right = evaluate_node(node.right, env)
    op = node.op
    if op == "+":
        return left + right
    if op == "-":
        return left - right
    if op == "*":
        return left * right
    if op == "/":
        if right == 0:
            raise error_at(EvalRuntimeError, "除数不能为零", "", node.token)
        return left / right
    if op == "%":
        if right == 0:
            raise error_at(EvalRuntimeError, "取模的除数不能为零", "", node.token)
        return left % right
    raise error_at(EvalRuntimeError, "不支持的运算符 %s" % op, "", node.token)


def eval(src, env=None):
    """求表达式字符串的值，返回 int 或 float。

    env 是变量到数值的字典或 None，不传时任何变量都算未定义。
    """
    node = parse(src)
    try:
        return evaluate_node(node, env)
    except EvalError as exc:
        # 语法树不记原文，求值层报出的错误在这里补回表达式以定位。
        if not exc.src:
            exc.src = src
        raise


# 显式别名，避免调用方写 effecteval.eval 时误以为是在调内建函数。
evaluate = eval
