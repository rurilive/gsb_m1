"""lagrange 现状演示。

第一段：几个小规模插值走一遍现有朴素能力，看点、范德蒙德方程组、朴素消元解出
的系数、逐项代入求值、多项式乘法、整数幂和的逐项枚举，以及解方程组与逐项求值
随规模增长的运算量对照；顺带看重复横坐标与空点集的诊断。
第二段：预留的拉格朗日插值路、牛顿差分路、分治与快速傅里叶乘法、秦九韶求值、
幂和闭式、反求系数与规模对照的演示位子。
"""

from fractions import Fraction

from lagrange import (
    LagrangeError,
    naive_eval,
    naive_eval_cost,
    naive_fit_coefficients,
    naive_mul,
    naive_power_sum,
    naive_solve_cost,
    naive_value_at,
    vandermonde_rows,
)

# 过 (0,1)、(1,3)、(2,7) 的多项式是 x^2 + x + 1
POINTS = [(0, 1), (1, 3), (2, 7)]


def main():
    print("=== 插值与多项式运算的朴素实现 ===")
    print("  插值点:", POINTS)
    rows = vandermonde_rows([(Fraction(x), Fraction(y)) for x, y in POINTS], 2)
    print("  范德蒙德增广行:", rows)
    coeffs = naive_fit_coefficients(POINTS)
    print("  朴素解出的系数:", coeffs)
    print("  代入 x=3 求值:", naive_eval(coeffs, 3),
          "  x=-1:", naive_eval(coeffs, -1),
          "  x=1/2:", naive_eval(coeffs, Fraction(1, 2)))
    print("  直接求 x=3 处的值:", naive_value_at(POINTS, 3))

    print("  多项式乘法 [1,1] 乘 [1,-1]:", naive_mul([1, 1], [1, -1]))
    print("  整数幂和 1^2+..+4^2:", naive_power_sum(4, 2),
          "  1+..+5:", naive_power_sum(5, 1))

    for count in (4, 8, 16):
        print("  点数", count, "朴素解方程运算量:", naive_solve_cost(count),
              " 次数", count - 1, "逐项求值运算量:", naive_eval_cost(count - 1))

    try:
        naive_fit_coefficients([(1, 2), (1, 5)])
    except LagrangeError as exc:
        print("  重复横坐标诊断:", exc.message)

    try:
        naive_value_at([], 0)
    except LagrangeError as exc:
        print("  空点集诊断:", exc.message)

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
