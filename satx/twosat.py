"""satx 的朴素实现（改造前基线）。

核心类 TwoSat 管一组布尔变量与若干二元的合取约束，每个约束是两个文字的或。
现状是把全部变量取值的组合逐一列出来，挨个判断哪一组能满足全部约束，
变量一多组合数就指数爆炸；判定、给方案、取某变量取值、数满足的约束条数，
全部都靠这套枚举兜底。功能是对的，规模一大就慢得离谱。
"""

from itertools import product


class SatError(Exception):
    """本库所有异常的基类。"""


class InvalidLiteralError(SatError, ValueError):
    """文字不合口径时抛出：为零、非整数、引用的变量下标越界。"""


class InvalidAssignmentError(SatError, ValueError):
    """赋值不合口径时抛出：缺项、变量越界、取值非布尔。"""


def _check_var_count(var_count):
    """变量个数必须是自然数。"""
    if isinstance(var_count, bool) or not isinstance(var_count, int):
        raise SatError("变量个数必须是整数")
    if var_count < 0:
        raise SatError("变量个数不能为负")
    return var_count


def _check_literal(literal, var_count):
    """文字用整数表示：正数表示变量取真，负数表示取反，零不合法。"""
    if isinstance(literal, bool) or not isinstance(literal, int):
        raise InvalidLiteralError("文字必须是整数，正数取真，负数取反")
    if literal == 0:
        raise InvalidLiteralError("文字不能为零")
    if abs(literal) > var_count:
        raise InvalidLiteralError("文字引用的变量下标越界")
    return literal


def _check_assignment(assignment, var_count):
    """赋值必须是覆盖全部变量的、变量到布尔值的完整映射。"""
    if not isinstance(assignment, dict):
        raise InvalidAssignmentError("赋值必须是变量到布尔值的映射")
    checked = {}
    for var, value in assignment.items():
        if isinstance(var, bool) or not isinstance(var, int):
            raise InvalidAssignmentError("赋值的键必须是变量下标")
        if var < 1 or var > var_count:
            raise InvalidAssignmentError("赋值引用了越界的变量")
        if not isinstance(value, bool):
            raise InvalidAssignmentError("变量的取值必须是布尔值")
        checked[var] = value
    if len(checked) != var_count:
        raise InvalidAssignmentError("赋值必须覆盖全部变量")
    return checked


class TwoSat:
    """二元合取约束组，用枚举全部赋值的方式求解。

    变量用从一到变量个数的整数编号。文字用带符号整数表示：正 k 表示变量 k
    取真，负 k 表示变量 k 取反。每个约束是两个文字的或，若干约束按合取叠加。
    """

    def __init__(self, var_count):
        self._n = _check_var_count(var_count)
        self._clauses = []

    def var_count(self):
        return self._n

    def add_clause(self, left, right):
        """追加一个两个文字的或作为约束，返回自身以便链式调用。"""
        a = _check_literal(left, self._n)
        b = _check_literal(right, self._n)
        self._clauses.append((a, b))
        return self

    def clauses(self):
        """取回约束列表，对外只读，保持加入顺序。"""
        return list(self._clauses)

    def clause_count(self):
        return len(self._clauses)

    def enumeration_size(self):
        """朴素路径要逐个检查的完整赋值个数，即二的变量个数次方。"""
        return 1 << self._n

    def _holds(self, literal, assignment):
        """某个文字在某组完整赋值下是否成立。"""
        value = assignment[abs(literal)]
        return value if literal > 0 else not value

    def _assignment_holds(self, assignment, clauses):
        """一组完整赋值是否满足全部约束。"""
        for a, b in clauses:
            if not (self._holds(a, assignment) or self._holds(b, assignment)):
                return False
        return True

    def _all_assignments(self):
        """按固定顺序枚举全部完整赋值：假在前真在后，变量编号从小到大。"""
        for values in product((False, True), repeat=self._n):
            yield {index + 1: values[index] for index in range(self._n)}

    def is_satisfiable(self):
        """逐个枚举完整赋值，只要有一组满足全部约束就为真。"""
        clauses = self._clauses
        for assignment in self._all_assignments():
            if self._assignment_holds(assignment, clauses):
                return True
        return False

    def solve(self):
        """按固定枚举顺序给出第一组满足全部约束的赋值，没有则返回 None。"""
        clauses = self._clauses
        for assignment in self._all_assignments():
            if self._assignment_holds(assignment, clauses):
                return assignment
        return None

    def value_of(self, var):
        """某变量在所选方案中的取值，判不出方案时返回 None。"""
        if isinstance(var, bool) or not isinstance(var, int):
            raise InvalidLiteralError("变量下标必须是整数")
        if var < 1 or var > self._n:
            raise InvalidLiteralError("变量下标越界")
        solution = self.solve()
        if solution is None:
            return None
        return solution[var]

    def satisfied_count(self, assignment):
        """给定完整赋值下被满足的约束条数。"""
        checked = _check_assignment(assignment, self._n)
        total = 0
        for a, b in self._clauses:
            if self._holds(a, checked) or self._holds(b, checked):
                total += 1
        return total

    def count_models(self):
        """枚举全部赋值，数出满足全部约束的赋值个数。"""
        clauses = self._clauses
        total = 0
        for assignment in self._all_assignments():
            if self._assignment_holds(assignment, clauses):
                total += 1
        return total
