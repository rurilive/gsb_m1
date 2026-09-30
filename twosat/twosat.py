"""twosat: 改造前的朴素二可满足性实现。

对外只暴露一组函数, 一切求解都靠对每个布尔变量枚举真与假, 再用全部子句
逐条验证是否满足, 变量一多就是二的变量数次方, 规模一大就慢到下不去手。

字面量用非零整数表示: 正整数 k 表示第 k 个变量取真, 负整数 -k 表示第 k 个
变量取假。子句是至少两个文字构成的序列, 变量个数记为 n, 变量编号从 1 到 n。
"""


class Erro(Exception):
    """本题所有异常的公共基类。"""


class BadVariableCountError(Erro):
    """变量个数不是非负整数时抛出。"""


class BadClauseError(Erro):
    """子句不是序列、文字少于两个或变量编号越界时抛出。"""


class BadLiteralError(Erro):
    """字面量不是非零整数时抛出。"""


class BadAssignmentError(Erro):
    """给定赋值结构不对时抛出。"""


class UnsatisfiableError(Erro):
    """要求给出解但不存在可行赋值时抛出。"""


def _check_var_count(n):
    if isinstance(n, bool) or not isinstance(n, int):
        raise BadVariableCountError("变量个数必须是整数: %r" % (n,))
    if n < 0:
        raise BadVariableCountError("变量个数不能为负: %r" % (n,))
    return n


def _check_literal(lit, n):
    if isinstance(lit, bool) or not isinstance(lit, int):
        raise BadLiteralError("字面量必须是整数: %r" % (lit,))
    if lit == 0:
        raise BadLiteralError("字面量不能为零: %r" % (lit,))
    if abs(lit) > n:
        raise BadLiteralError("字面量编号越界: %r" % (lit,))
    return lit


def _check_clause(clause, n):
    if not isinstance(clause, (tuple, list)):
        raise BadClauseError("子句必须是序列: %r" % (clause,))
    if len(clause) < 2:
        raise BadClauseError("子句至少两个文字: %r" % (clause,))
    out = []
    for lit in clause:
        out.append(_check_literal(lit, n))
    return out


def _check_clauses(clauses, n):
    if not isinstance(clauses, (tuple, list)):
        raise BadClauseError("子句集合必须是序列: %r" % (clauses,))
    return [_check_clause(c, n) for c in clauses]


def _assignment_from_mask(n, mask):
    """把枚举位转成变量编号到真假的映射。

    枚举口径写死: 变量编号一到 n 依次放在枚举位的低位到高位, 位零为假、
    位一为真。同一输入下这个映射唯一, 不依赖任何模块级可变状态。
    """
    assign = {}
    for v in range(1, n + 1):
        assign[v] = bool((mask >> (v - 1)) & 1)
    return assign


def _clause_ok(clause, assign):
    for lit in clause:
        if assign[abs(lit)] == (lit > 0):
            return True
    return False


def _all_ok(clauses, assign):
    for clause in clauses:
        if not _clause_ok(clause, assign):
            return False
    return True


def normalize_assignment(n, assign):
    """把赋值规整成变量编号到真假的字典, 结构不对立刻报错。"""
    _check_var_count(n)
    if not isinstance(assign, dict):
        raise BadAssignmentError("赋值必须是字典: %r" % (assign,))
    if len(assign) != n:
        raise BadAssignmentError("赋值规模不对: %r" % (len(assign),))
    out = {}
    for v in range(1, n + 1):
        if v not in assign:
            raise BadAssignmentError("缺少变量: %r" % (v,))
        val = assign[v]
        if isinstance(val, bool):
            out[v] = val
        elif isinstance(val, int) and (val == 0 or val == 1):
            out[v] = val == 1
        else:
            raise BadAssignmentError("取值必须是真假: %r" % (val,))
    return out


def verify(n, clauses, assign):
    """给定赋值是否满足全部子句。"""
    _check_var_count(n)
    checked = _check_clauses(clauses, n)
    normalized = normalize_assignment(n, assign)
    return _all_ok(checked, normalized)


def solve(n, clauses):
    """朴素求解: 枚举变量真假, 逐条验证子句, 返回第一个可行赋值或 None。

    枚举从全假开始按枚举位递增, 因此同一输入必然给出同一组解。
    """
    _check_var_count(n)
    checked = _check_clauses(clauses, n)
    for mask in range(1 << n):
        assign = _assignment_from_mask(n, mask)
        if _all_ok(checked, assign):
            return assign
    return None


def is_satisfiable(n, clauses):
    """是否存在可行赋值。"""
    return solve(n, clauses) is not None


def count_solutions(n, clauses):
    """可行赋值的总数, 完全靠枚举统计。"""
    _check_var_count(n)
    checked = _check_clauses(clauses, n)
    total = 0
    for mask in range(1 << n):
        assign = _assignment_from_mask(n, mask)
        if _all_ok(checked, assign):
            total += 1
    return total


def require_solution(n, clauses):
    """要求给出可行赋值, 不存在时抛 UnsatisfiableError。"""
    result = solve(n, clauses)
    if result is None:
        raise UnsatisfiableError("该公式没有可行赋值: n=%r" % (n,))
    return result
