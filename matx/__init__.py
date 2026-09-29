"""matx：朴素整数矩阵工具（改造前基线）。

提供 NaiveMat 类，把方阵用二维列表存起来，支持逐项相乘、求幂、
逐项相加，另有一组模块级函数提供零矩阵、单位矩阵、对角矩阵的构造，
以及用连续迭代求斐波那契数的 fib。

当前实现全部走最直白的循环：乘法是三重循环的立方级，矩阵幂靠连续
自乘因而需要与指数同量级的乘法次数，斐波那契靠逐个递推因而需要与
下标同量级的加法次数。做法直观可靠，但规模一大就明显吃力，也没有
任何把乘加次数量出来的手段。
"""

from .mat import (
    IndexError,
    InvalidModuloError,
    MatError,
    NaiveMat,
    ShapeError,
    fib,
    mat_add,
    mat_diagonal,
    mat_identity,
    mat_mul,
    mat_power,
    mat_zeros,
)

__all__ = [
    "MatError",
    "ShapeError",
    "IndexError",
    "InvalidModuloError",
    "NaiveMat",
    "mat_zeros",
    "mat_identity",
    "mat_diagonal",
    "mat_mul",
    "mat_add",
    "mat_power",
    "fib",
]
