"""simplexlp：线性规划求解的朴素工具箱。

当前对外能力是几个直白函数：把若干不等式约束两两相交得到候选交点，逐个
代入全部约束筛掉不可行的，再比目标值挑最大的那个；顺带判断一个点在约束下
可不可行、目标值是多少，以及列出一批约束覆盖过哪些变量。约束一多，两两
相交的候选集就是组合量级，一大就跑不动，也还没法说清有界无界、有没有解。
"""

from .vertex import (
    EPS,
    OBJECTIVE_ALL_ZERO,
    STATUS_FEASIBLE,
    STATUS_INFEASIBLE,
    STATUS_OPTIMAL,
    STATUS_UNBOUNDED,
    LinearProgramError,
    all_constraint_pairs,
    as_fraction,
    naive_covered_variables,
    naive_is_feasible,
    naive_maximize,
    naive_objective_value,
    naive_optimize,
    naive_status,
    naive_vertex_count,
    point_value,
    refine_intersection,
    to_fraction,
    variables_seen,
)

__all__ = [
    "EPS",
    "OBJECTIVE_ALL_ZERO",
    "STATUS_FEASIBLE",
    "STATUS_INFEASIBLE",
    "STATUS_OPTIMAL",
    "STATUS_UNBOUNDED",
    "LinearProgramError",
    "all_constraint_pairs",
    "as_fraction",
    "naive_covered_variables",
    "naive_is_feasible",
    "naive_maximize",
    "naive_objective_value",
    "naive_optimize",
    "naive_status",
    "naive_vertex_count",
    "point_value",
    "refine_intersection",
    "to_fraction",
    "variables_seen",
]
