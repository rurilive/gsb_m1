"""chainkit：矩阵链最优加括号方案与派生问题的工具箱。

当前对外能力是一组朴素函数：算区间最少与最大乘法次数、给对应的一个方案、
数最少次数的方案个数、判定链是否合法、求多边形三角剖分最低代价、在括号串与
方案之间来回。区间递推、回溯重建、枚举交叉核对这些都留待在这个基础上补齐。
"""

from .chain import (
    ChainError,
    check_dims,
    feasible,
    is_feasible,
    naive_cost,
    naive_count,
    naive_max_cost,
    naive_max_optimal,
    naive_optimal,
    naive_plan_cost,
    naive_triangle,
    parse_plan,
    plan_to_string,
    whole_cost,
    whole_count,
    whole_max_cost,
    whole_max_optimal,
    whole_optimal,
)

__all__ = [
    "ChainError",
    "check_dims",
    "feasible",
    "is_feasible",
    "naive_cost",
    "naive_count",
    "naive_max_cost",
    "naive_max_optimal",
    "naive_optimal",
    "naive_plan_cost",
    "naive_triangle",
    "parse_plan",
    "plan_to_string",
    "whole_cost",
    "whole_count",
    "whole_max_cost",
    "whole_max_optimal",
    "whole_optimal",
]
