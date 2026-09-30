"""lagrange：插值与多项式运算的朴素工具箱。

当前对外能力都是最直白的循环实现：给定若干点求过这些点的多项式在某点的
取值时，先列范德蒙德方程组解出系数再逐项代入；多项式乘法两两双重循环；多项式
求值逐项累乘；整数幂和的闭式值靠逐项枚举。样例点数一多，解方程组与逐项求值
的量级立刻压得跑不动。
"""

from .interp import (
    LagrangeError,
    naive_eval,
    naive_eval_cost,
    naive_fit_coefficients,
    naive_mul,
    naive_power_sum,
    naive_solve_cost,
    naive_value_at,
    normalize_points,
    solve_linear_system,
    to_fraction,
    vandermonde_rows,
)

__all__ = [
    "LagrangeError",
    "naive_eval",
    "naive_eval_cost",
    "naive_fit_coefficients",
    "naive_mul",
    "naive_power_sum",
    "naive_solve_cost",
    "naive_value_at",
    "normalize_points",
    "solve_linear_system",
    "to_fraction",
    "vandermonde_rows",
]
