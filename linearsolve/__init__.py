"""linearsolve：线性方程组求解的朴素工具箱。

当前对外能力是一组直白函数：把增广矩阵按最朴素的主元消元、由最后一行
看方程组有没有解、用递归展开算行列式、把线性方程组写成矩阵形式。这些
都只在小规模上跑得动，规模一大就慢，主元与数值口径也没定下来，留待
在这个基础上补齐。
"""

from .solve import (
    LinearSolveError,
    MATRIX_SEPARATOR,
    build_augmented,
    naive_determinant,
    naive_free_symbols,
    naive_is_consistent,
    naive_rank,
    naive_solve,
    naive_solve_matrix,
    parse_matrix_text,
)

__all__ = [
    "LinearSolveError",
    "MATRIX_SEPARATOR",
    "build_augmented",
    "naive_determinant",
    "naive_free_symbols",
    "naive_is_consistent",
    "naive_rank",
    "naive_solve",
    "naive_solve_matrix",
    "parse_matrix_text",
]
