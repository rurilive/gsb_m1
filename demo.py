"""linearsolve 现状演示。

第一段：一小组线性方程组走一遍现有朴素能力，看唯一解、无穷多解、无解三种
判定，看求秩、求行列式、自由变量，以及从矩阵文本解析与拼增广矩阵。
第二段：预留的选主元、约当回代、模素数域印证与规模对照的演示位子。
"""

from fractions import Fraction

from linearsolve import (
    LinearSolveError,
    build_augmented,
    naive_determinant,
    naive_free_symbols,
    naive_is_consistent,
    naive_rank,
    naive_solve,
    naive_solve_matrix,
    parse_matrix_text,
)
from linearsolve.solve import elimination_ops, expansion_ops

UNIQUE3 = [[2, 1, -1, 8], [-3, -1, 2, -11], [-2, 1, 2, -3]]
SINGULAR = [[1, 2, 3], [2, 4, 6]]
NONE = [[1, 2, 3], [2, 4, 7]]


def main():
    print("=== 线性方程组的朴素求解 ===")
    print("  三阶方程组:", UNIQUE3)
    status, solution = naive_solve_matrix(UNIQUE3)
    print("  状态:", status, " 解:", solution)
    print("  秩:", naive_rank(UNIQUE3))
    print("  行列式:", naive_determinant([[2, 1, -1, 0], [-3, -1, 2, 0], [-2, 1, 2, 0]]))

    print("  两个方程成比例:", SINGULAR)
    print("  状态:", naive_solve_matrix(SINGULAR)[0],
          " 有无解:", naive_is_consistent(SINGULAR),
          " 秩:", naive_rank(SINGULAR))
    print("  自由变量列:", naive_free_symbols(SINGULAR))

    print("  系数成比例而常数项不:", NONE)
    print("  状态:", naive_solve_matrix(NONE)[0],
          " 有无解:", naive_is_consistent(NONE))

    frac = [[2, 0, 1], [0, 3, 1]]
    print("  分数解:", naive_solve(frac))

    grid = parse_matrix_text("1 2 | 3\n4 5 | 6")
    print("  文本解析:", grid)
    print("  拼增广:", build_augmented([[1, 2], [3, 4]], [5, 6]))

    print("  消元比较次数 5 阶方阵:", elimination_ops(5, 5))
    print("  朴素展开项数 5 阶:", expansion_ops(5))

    for bad in ([], [[1, 2, 3], [4, 5]], [[1], [2]]):
        try:
            naive_rank(bad)
        except LinearSolveError as exc:
            print("  非法矩阵的诊断:", exc.message)

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
