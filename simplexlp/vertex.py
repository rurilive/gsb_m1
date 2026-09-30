"""vertex：线性规划的朴素顶点枚举。

把线性规划写成一组小于等于形式的约束，再加上每个变量非负、目标取最大。
这里用最直白的办法求最优：枚举任意两条约束相交得到的点，逐个代回全部约束
看可不可行，可行的里面留目标值最大的那个。约束个数一多，两条一组的组合数
就是组合量级，规模一大就跑不动。数值上按分数精确算，不做浮点近似。
"""

from fractions import Fraction
from itertools import combinations

# 判零用的容差。分数精确算术下本不需要，但输入可能是浮点或长的小数，留一个
# 小阈值挡住二进制表示带来的微小残差。
EPS = Fraction(1, 10 ** 12)

# 目标系数全为零时的状态标记：此时任何可行点目标值都是零，没有可挑的最优点。
OBJECTIVE_ALL_ZERO = "objective_all_zero"

# 求解状态
STATUS_OPTIMAL = "optimal"
STATUS_UNBOUNDED = "unbounded"
STATUS_INFEASIBLE = "infeasible"
STATUS_FEASIBLE = "feasible"


class LinearProgramError(Exception):
    """本模块所有可诊断错误的基类。"""

    def __init__(self, message, position=None, data=None):
        super().__init__(message)
        self.message = message
        self.position = position
        self.data = data


def to_fraction(value):
    """把整数、分数或浮点统一转成分数。布尔值拒绝，别的没见过的类型也拒绝。"""
    if isinstance(value, bool):
        raise LinearProgramError("布尔不能当作系数", data=value)
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, float):
        return Fraction(value)
    raise LinearProgramError("系数只能是整数、分数或浮点", data=value)


def as_fraction(value):
    """to_fraction 的别名，给读代码的人一个更顺口的名字。"""
    return to_fraction(value)


def _check_coefficients(coeffs, position):
    if not isinstance(coeffs, (list, tuple)) or not coeffs:
        raise LinearProgramError("约束系数不能为空", position=position)
    return [to_fraction(c) for c in coeffs]


def _parse_constraint(constraint, position):
    """约束可以写成二元组(系数表, 常数)或三元组(系数表, 常数, 方向)。

    方向只认小于等于。写成别的方向直接拒绝，因为这里的解法只处理小于等于。
    """
    if not isinstance(constraint, (list, tuple)):
        raise LinearProgramError("约束要是二元组或三元组", position=position)
    if len(constraint) == 2:
        coeffs, bound = constraint
        sense = "<="
    elif len(constraint) == 3:
        coeffs, bound, sense = constraint
        if sense not in ("<=", "<", "le"):
            raise LinearProgramError("只处理小于等于方向的约束", position=position)
        sense = "<="
    else:
        raise LinearProgramError("约束的长度只能是二或三", position=position)
    return _check_coefficients(coeffs, position), to_fraction(bound), sense


def _parse_problem(constraints, objective):
    """把约束与目标都过一遍格式，返回规整后的列表。"""
    if not isinstance(constraints, (list, tuple)):
        raise LinearProgramError("约束集合要是列表或元组", position=-1)
    rows = []
    for i, raw in enumerate(constraints):
        rows.append(_parse_constraint(raw, i))
    if not isinstance(objective, (list, tuple)):
        raise LinearProgramError("目标系数要是列表或元组", position=-1)
    obj = [to_fraction(c) for c in objective]
    return rows, obj


def variables_seen(constraints):
    """列出这批约束一共覆盖过哪些变量下标，按下标从小到大排。"""
    rows, _ = _parse_problem(constraints, [])
    seen = set()
    for coeffs, _bound, _sense in rows:
        for j, c in enumerate(coeffs):
            if c != 0:
                seen.add(j)
    return sorted(seen)


def _width(rows):
    width = 0
    for coeffs, _bound, _sense in rows:
        if len(coeffs) > width:
            width = len(coeffs)
    return width


def _pad(coeffs, width):
    out = list(coeffs)
    while len(out) < width:
        out.append(Fraction(0))
    return out


def _objective_value(obj, point):
    width = len(point)
    value = Fraction(0)
    for j, c in enumerate(obj):
        if j < width:
            value += to_fraction(c) * point[j]
    return value


def point_value(objective, point):
    """给定点的目标值，用于外部朴素地核一遍。"""
    if not isinstance(point, (list, tuple)):
        raise LinearProgramError("点要是列表或元组", position=-1)
    vec = [to_fraction(x) for x in point]
    return _objective_value(objective, vec)


def _is_feasible(rows, width, point):
    """点要每一项非负，且代进每条约束都落在常数以内。"""
    if len(point) < width:
        return False
    for x in point:
        if x < -EPS:
            return False
    for coeffs, bound, _sense in rows:
        lhs = Fraction(0)
        padded = _pad(coeffs, width)
        for j in range(width):
            lhs += padded[j] * point[j]
        if lhs > bound + EPS:
            return False
    return True


def _solve_2x2(a1, b1, c1, a2, b2, c2):
    """两条直线求交点。平行时给出 None。"""
    det = a1 * b2 - a2 * b1
    if det == 0:
        return None
    x = (c1 * b2 - c2 * b1) / det
    y = (a1 * c2 - a2 * c1) / det
    return x, y


def refine_intersection(first, second, width):
    """两条约束的系数直接两两消元求交点，最多覆盖前两个变量。

    这是最朴素的直线求交，只处理两个变量的情形，多余变量一律当零；两条平行
    或者重合就给 None。规模与覆盖面都有限，留待在这个基础上补齐。
    """
    rows, _ = _parse_problem([first, second], [])
    coeffs1, bound1, _s1 = rows[0]
    coeffs2, bound2, _s2 = rows[1]
    a1 = coeffs1[0] if len(coeffs1) > 0 else Fraction(0)
    b1 = coeffs1[1] if len(coeffs1) > 1 else Fraction(0)
    a2 = coeffs2[0] if len(coeffs2) > 0 else Fraction(0)
    b2 = coeffs2[1] if len(coeffs2) > 1 else Fraction(0)
    hit = _solve_2x2(a1, b1, bound1, a2, b2, bound2)
    if hit is None:
        return None
    point = [Fraction(0)] * width
    point[0] = hit[0]
    if width > 1:
        point[1] = hit[1]
    return point


def all_constraint_pairs(constraints):
    """枚举约束的两两组合，返回下标对。条数少时是常数级，条数一多就是组合量级。"""
    count = len(constraints)
    return list(combinations(range(count), 2))


def _collect_lattice(rows, obj, width):
    """朴素候选点的兜底来源：每个变量在零与各约束常数之间试一把。

    这只在单变量与小规模上看着对，多个变量同时取非零的情形覆盖不到。
    """
    levels = {Fraction(0)}
    for coeffs, bound, _sense in rows:
        for c in coeffs:
            if c == 0:
                continue
            levels.add(bound / c)
    ordering = sorted(levels)
    return ordering


def _candidate_points(rows, obj, width):
    """把所有候选点凑齐：两两相交的点，加上各坐标轴上的朴素兜底点。"""
    points = []
    index = 0
    for i, j in all_constraint_pairs(rows):
        hit = refine_intersection(rows[i], rows[j], width)
        if hit is not None:
            points.append(hit)
        index += 1
    if not rows:
        points.append([Fraction(0)] * width)
        return points
    lattice = _collect_lattice(rows, obj, width)
    # 兜底点：只让第一个变量扫一遍候选水位，其余变量取零。
    for level in lattice:
        point = [Fraction(0)] * width
        if width > 0:
            point[0] = level
        points.append(point)
    return points


def _status_for(rows, obj, width, best_point, best_value):
    """从最终结果反推状态，供外部朴素地核一遍。"""
    if best_point is not None:
        return STATUS_OPTIMAL
    for _coeffs, bound, _sense in rows:
        if bound < -EPS:
            return STATUS_INFEASIBLE
    return STATUS_INFEASIBLE


def _solve_naive(constraints, objective):
    """核心朴素解：枚举候选点、筛可行、挑目标最大。

    这是组合量级的主力：约束个数每加一条，两两组合就多出一整行。
    """
    rows, obj = _parse_problem(constraints, objective)
    width = _width(rows)
    if width == 0:
        width = len(obj)
    if width == 0:
        raise LinearProgramError("问题里没有任何变量", position=-1)

    candidates = _candidate_points(rows, obj, width)
    best_point = None
    best_value = None
    for point in candidates:
        if not _is_feasible(rows, width, point):
            continue
        value = _objective_value(obj, point)
        if best_value is None or value > best_value:
            best_value = value
            best_point = list(point)
    return rows, obj, width, best_point, best_value


def naive_optimize(constraints, objective):
    """朴素求解：返回(状态, 最优值, 最优顶点)。

    状态是 optimal 或 infeasible。无界、多解、冗余这些情形现在一律看不出来，
    有界可行就报一个挑到的顶点。
    """
    rows, obj, width, best_point, best_value = _solve_naive(constraints, objective)
    if best_point is not None:
        return STATUS_OPTIMAL, best_value, best_point
    return STATUS_INFEASIBLE, None, None


def naive_maximize(constraints, objective):
    """只管目标最大值的顺手入口，给最常用的一步调用。"""
    _status, value, _point = naive_optimize(constraints, objective)
    return value


def naive_status(constraints, objective):
    """只要状态的顺手入口。"""
    status, _value, _point = naive_optimize(constraints, objective)
    return status


def naive_is_feasible(constraints, point):
    """点是否可行：每一项非负、且代进每条约束都不越界。"""
    rows, _ = _parse_problem(constraints, [])
    width = _width(rows)
    if width == 0:
        width = len(point)
    vec = [to_fraction(x) for x in point]
    return _is_feasible(rows, width, vec)


def naive_covered_variables(constraints):
    """这批约束覆盖过哪些变量下标，等价于上面 variables_seen 的朴素名。"""
    return variables_seen(constraints)


def naive_vertex_count(constraints):
    """枚举候选点时会看多少对约束，露出组合量级的规模。"""
    rows, _ = _parse_problem(constraints, [])
    return len(all_constraint_pairs(rows))


def naive_objective_value(objective, point):
    """给定点在目标下的取值，与 point_value 同一口径。"""
    return point_value(objective, point)
