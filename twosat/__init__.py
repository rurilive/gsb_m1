"""twosat: 改造前的朴素二可满足性实现。

对外只暴露 solve、verify、is_satisfiable、count_solutions 与异常基类,
一切求解都靠对每个布尔变量枚举真与假, 再用全部子句逐条验证。
"""
from .twosat import (
    Erro,
    BadVariableCountError,
    BadClauseError,
    BadLiteralError,
    BadAssignmentError,
    UnsatisfiableError,
    solve,
    verify,
    is_satisfiable,
    count_solutions,
    require_solution,
)

__all__ = [
    "Erro",
    "BadVariableCountError",
    "BadClauseError",
    "BadLiteralError",
    "BadAssignmentError",
    "UnsatisfiableError",
    "solve",
    "verify",
    "is_satisfiable",
    "count_solutions",
    "require_solution",
]
