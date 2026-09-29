"""effecteval：一个带变量绑定的算术表达式求值器，纯标准库。

当前对外能力是 eval：对四则运算、取模、一元正负与括号组成的表达式求值，
变量值由调用方以字典传入。依赖跟踪、记忆化失效、副作用记录与重放、惰性短路、
事务回滚与并发隔离都留待在这个基础上补齐。
"""

from .eval import eval, evaluate, evaluate_node
from .errors import EvalError, EvalRuntimeError, ParseError
from .lexer import tokenize
from .parser import parse

__all__ = [
    "EvalError",
    "EvalRuntimeError",
    "ParseError",
    "eval",
    "evaluate",
    "evaluate_node",
    "parse",
    "tokenize",
]
