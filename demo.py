"""simplexlp 现状演示。

第一段：一组小规模线性规划走一遍现有朴素能力，看枚举约束两两相交的候选点、
代入全部约束筛可行、比目标值挑最大，看可行判定、目标值、覆盖变量与组合量级
的候选对数；顺带看两条约束直接求交的朴素入口。
第二段：预留的单纯形法、分数精确顶点枚举、对偶与紧约束检验、退化情形与规模
对照的演示位子。
"""

from fractions import Fraction

from simplexlp import (
    LinearProgramError,
    all_constraint_pairs,
    naive_covered_variables,
    naive_is_feasible,
    naive_objective_value,
    naive_optimize,
    naive_vertex_count,
    refine_intersection,
    to_fraction,
)

# 最大化 3x+2y，约束 x+y<=4、x<=3、y<=3，变量非负。朴素枚举该找出 (3,1)。
CONSTRAINTS = [
    ([1, 1], 4),
    ([1, 0], 3),
    ([0, 1], 3),
]
OBJECTIVE = [3, 2]

# 一条常数项为负的约束在非负变量下永远取不到，朴素只会报不可行。
INFEASIBLE = [([1, 1], -1)]


def main():
    print("=== 线性规划的朴素顶点枚举 ===")
    print("  约束:", CONSTRAINTS, " 目标:", OBJECTIVE)
    status, value, point = naive_optimize(CONSTRAINTS, OBJECTIVE)
    print("  状态:", status, " 最优值:", value, " 最优顶点:", point)

    print("  候选对数:", naive_vertex_count(CONSTRAINTS),
          " 组合:", all_constraint_pairs(CONSTRAINTS))
    print("  覆盖变量:", naive_covered_variables(CONSTRAINTS))

    probe = [Fraction(2), Fraction(1)]
    print("  点", probe, "可行:", naive_is_feasible(CONSTRAINTS, probe),
          " 目标值:", naive_objective_value(OBJECTIVE, probe))

    print("  两条约束求交:", refine_intersection(([1, 1], 4), ([1, 0], 3), 2))
    print("  两条平行约束求交:", refine_intersection(([1, 1], 4), ([2, 2], 8), 2))

    print("  无可行解的一组:", INFEASIBLE)
    print("  状态:", naive_optimize(INFEASIBLE, OBJECTIVE)[0])

    print("  分数系数:", to_fraction(Fraction(1, 3)), to_fraction(2))

    for bad in ([[1, 2], 3, ">="], ("oops",), [[True, 1], 2]):
        try:
            naive_optimize([bad], OBJECTIVE)
        except LinearProgramError as exc:
            print("  非法输入诊断:", exc.message)

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
