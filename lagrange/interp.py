"""插值与多项式运算的朴素实现。

这一层只解决"结果对"：给若干点求过这些点的多项式在某点的取值，走的是先列
范德蒙德方程组、用朴素高斯消元解出系数、再逐项累乘代入的老路；多项式乘法是
两两双重循环；多项式求值逐项累乘；整数幂和的闭式值靠逐项枚举。次数一高或点
数一多，解方程组的量级与逐项求值的量级就压得跑不动，但每一步都老老实实，
不给近似，全程用分数精确算。

对外错误统一继承 LagrangeError，报错带上出错的位置与说明。
"""

from fractions import Fraction

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


class LagrangeError(Exception):
    """本工具包所有可诊断错误的基类。

    字段：message 说明出了什么事；position 指出出错的位置（第几个插值点、
    哪一行方程、哪一个系数），没有位置时为 None；data 附带定位用的原始数据。
    """

    def __init__(self, message, position=None, data=None):
        super().__init__(message)
        self.message = message
        self.position = position
        self.data = data

    def __str__(self):
        if self.position is None:
            return self.message
        return "{}（位置：{}）".format(self.message, self.position)


def to_fraction(value):
    """把整数、分数或浮点转成 Fraction 精确值；布尔与非数一律报错。

    浮点只在入口处按二进制精确值转一次，之后全程不再出现浮点。
    """
    if isinstance(value, bool):
        raise LagrangeError("布尔不能当系数用", data=value)
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, float):
        return Fraction(value)
    raise LagrangeError("不认识的数值类型：{}".format(type(value).__name__), data=value)


def normalize_points(points):
    """把插值点规整成 (Fraction, Fraction) 列表，顺便校验合法性。

    每个点必须是一对横纵坐标；横坐标不得重复，否则无唯一多项式可解；
    空点集直接报错，因为过零个点的多项式不存在。
    """
    if points is None:
        raise LagrangeError("插值点不能为空", data=points)
    items = list(points)
    if not items:
        raise LagrangeError("插值点不能为空")
    normalized = []
    seen = set()
    for index, pair in enumerate(items):
        try:
            x, y = pair
        except (TypeError, ValueError):
            raise LagrangeError("插值点必须是横纵一对", position=index, data=pair)
        fx = to_fraction(x)
        fy = to_fraction(y)
        if fx in seen:
            raise LagrangeError(
                "插值点横坐标重复，无唯一多项式", position=index, data=pair
            )
        seen.add(fx)
        normalized.append((fx, fy))
    return normalized


def vandermonde_rows(points, degree):
    """按点与度数铺出范德蒙德方程组的增广行。

    第 i 个点给出 [1, x, x^2, ...] 乘上未知系数等于 y 的一行，全部按分数精确保存。
    """
    if degree < 0:
        raise LagrangeError("多项式次数不能为负", data=degree)
    rows = []
    for index, (x, y) in enumerate(points):
        row = [Fraction(1)]
        current = Fraction(1)
        for _ in range(degree):
            current = current * x
            row.append(current)
        row.append(y)
        rows.append(row)
    return rows


def solve_linear_system(rows, variables):
    """朴素高斯消元解线性方程组，返回未知数取值列表。

    每行是增广行，前 variables 个数是系数、最后一个是右端。消元直接按当前行
    顺序选主元，主元为零就报错；这是一条最直白、次数一高就慢的路径。
    """
    if variables <= 0:
        raise LagrangeError("未知数个数必须为正", data=variables)
    matrix = [[to_fraction(cell) for cell in row] for row in rows]
    if len(matrix) != variables:
        raise LagrangeError(
            "方程个数与未知数个数不相等，无法唯一求解",
            data=(len(matrix), variables),
        )
    for column in range(variables):
        pivot = matrix[column][column]
        if pivot == 0:
            raise LagrangeError("主元为零，朴素消元无法继续", position=column)
        for row in range(variables):
            if row == column:
                continue
            if matrix[row][column] == 0:
                continue
            factor = matrix[row][column] / pivot
            for k in range(column, variables + 1):
                matrix[row][k] -= factor * matrix[column][k]
    solution = []
    for i in range(variables):
        solution.append(matrix[i][variables] / matrix[i][i])
    return solution


def naive_fit_coefficients(points, degree=None):
    """朴素求过这些点的多项式系数，低次在前。

    先铺范德蒙德方程组，再调朴素消元解系数；点数定死了能解出的次数，显式给出
    的次数若与点数不匹配就报错。点数一大，这个方程组的规模与消元的量级就上
    来了，这是当前唯一的路。
    """
    normalized = normalize_points(points)
    count = len(normalized)
    if degree is None:
        degree = count - 1
    if degree < 0:
        raise LagrangeError("多项式次数不能为负", data=degree)
    if degree + 1 != count:
        raise LagrangeError(
            "请求的次数与点数不匹配，方程组无唯一解",
            data=(degree, count),
        )
    rows = vandermonde_rows(normalized, degree)
    return solve_linear_system(rows, degree + 1)


def naive_eval(coefficients, x):
    """逐项累乘求多项式在某点的值，低次在前。

    第 i 项要把 x 自乘 i 次再乘系数，最后累加；项数一多，重复自乘就堆上来了。
    """
    value = to_fraction(x)
    total = Fraction(0)
    for index, coefficient in enumerate(coefficients):
        power = Fraction(1)
        for _ in range(index):
            power = power * value
        total += to_fraction(coefficient) * power
    return total


def naive_value_at(points, x):
    """给定插值点，先解出系数再逐项代入，求多项式在 x 处的取值。"""
    coefficients = naive_fit_coefficients(points)
    return naive_eval(coefficients, x)


def naive_mul(left, right):
    """多项式乘法，两个循环逐对相乘再按次数累加，低次在前。"""
    a = [to_fraction(c) for c in left]
    b = [to_fraction(c) for c in right]
    if not a or not b:
        return []
    product = [Fraction(0)] * (len(a) + len(b) - 1)
    for i, ai in enumerate(a):
        for j, bj in enumerate(b):
            product[i + j] += ai * bj
    return product


def naive_power_sum(n, k):
    """连续整点幂和：从一到 n 的每个整数各取 k 次幂再累加，逐项枚举。"""
    if isinstance(n, bool) or isinstance(k, bool):
        raise LagrangeError("幂和的参数不能是布尔", data=(n, k))
    if not isinstance(n, int) or not isinstance(k, int):
        raise LagrangeError("幂和的上下限与次数都必须是整数", data=(n, k))
    if n < 0:
        raise LagrangeError("幂和上限不能为负", data=n)
    if k < 0:
        raise LagrangeError("幂和次数不能为负", data=k)
    total = Fraction(0)
    for i in range(1, n + 1):
        term = Fraction(1)
        for _ in range(k):
            term = term * i
        total += term
    return total


def naive_solve_cost(count):
    """朴素解方程组随点数增长的运算量对照：三次量级。"""
    if count < 0:
        raise LagrangeError("点数不能为负", data=count)
    return count * count * count


def naive_eval_cost(degree):
    """逐项累乘求值随次数增长的运算量对照：两两量级。"""
    if degree < 0:
        raise LagrangeError("次数不能为负", data=degree)
    return (degree + 1) * degree // 2
