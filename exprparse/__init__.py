"""exprparse：算术表达式解析与求值工具包，当前只有最朴素的一条路。

对外类 Expression 靠优先级从低到高反复扫描字符串、逐段切片、递归重建来完成
求值、中缀转后缀与批量求值；既没有词法单元化的记号概念，也没有调度场或递归下降
这类一趟走完的解析路径。括号一多字符串副本成倍增加，一大就慢，但结果是对的。
见 exprparse/engine.py。升级方向见任务描述与 README。
"""

from exprparse.engine import (
    ExprError,
    InvalidSyntaxError,
    UnbalancedParenError,
    DivisionByZeroError,
    UnknownVariableError,
    EmptyExpressionError,
    Expression,
)

__all__ = [
    "ExprError",
    "InvalidSyntaxError",
    "UnbalancedParenError",
    "DivisionByZeroError",
    "UnknownVariableError",
    "EmptyExpressionError",
    "Expression",
]
