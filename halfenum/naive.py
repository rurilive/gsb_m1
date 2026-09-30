"""halfenum 改造前的朴素实现。

子集搜索工具包：求容量上限内的最大子集和、求子集和恰好等于目标值的
字典序最小方案、统计可达子集和个数、把一个集合均分成两组求组和之差。
全部用最直白的位掩码枚举，逐个检查 2 的 n 次方个子集，规模一大就慢，
但结果正确，作为后续折半枚举与双向搜索改造前的事实基线。
"""


class HalfEnumError(ValueError):
    """本包全部可诊断错误的基类。"""


class InvalidInput(HalfEnumError):
    """入参类型或取值不合法。"""


def _check_values(values):
    """把入参规整成整数列表，非整数序列抛 InvalidInput。"""
    if isinstance(values, (str, bytes)):
        raise InvalidInput("values 必须是整数序列")
    try:
        seq = list(values)
    except TypeError:
        raise InvalidInput("values 必须是可迭代的整数序列")
    for item in seq:
        if isinstance(item, bool) or not isinstance(item, int):
            raise InvalidInput("集合元素必须都是整数")
    return seq


def _check_int(name, value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidInput("%s 必须是整数" % name)
    return value


def naive_enumeration_count(n):
    """位掩码全枚举在 n 个元素上要检查的子集个数，即 2 的 n 次方。"""
    n = _check_int("n", n)
    if n < 0:
        raise InvalidInput("n 不能为负")
    return 1 << n


def iter_subsets(values):
    """按位掩码从 0 到 2 的 n 次方减一逐个枚举子集。

    每个子集产出升序的下标元组，顺序与掩码递增顺序一致。
    """
    seq = _check_values(values)
    n = len(seq)
    for mask in range(1 << n):
        yield tuple(i for i in range(n) if mask & (1 << i))


def max_subset_sum(values, capacity):
    """求不超过容量上限的最大子集和，空子集和记为 0。

    容量必须是非负整数，否则抛 InvalidInput。
    """
    seq = _check_values(values)
    capacity = _check_int("capacity", capacity)
    if capacity < 0:
        raise InvalidInput("capacity 不能为负")
    best = 0
    for indices in iter_subsets(seq):
        total = sum(seq[i] for i in indices)
        if total <= capacity and total > best:
            best = total
    return best


def subset_sum_solution(values, target):
    """求子集和恰好等于目标值的方案。

    返回一组升序下标元组，多解时取下标序列字典序最小的那条；
    凑不出时返回 None。目标值必须是整数。
    """
    seq = _check_values(values)
    target = _check_int("target", target)
    best = None
    for indices in iter_subsets(seq):
        if sum(seq[i] for i in indices) == target:
            if best is None or indices < best:
                best = indices
    return best


def count_achievable_sums(values):
    """统计所有子集能得到多少个不同的和值，空子集的和 0 计入。"""
    seq = _check_values(values)
    sums = set()
    for indices in iter_subsets(seq):
        sums.add(sum(seq[i] for i in indices))
    return len(sums)


def group_difference(values, mode="min"):
    """把一个集合均分成两组，求两组和之差绝对值的最小值或最大值。

    分组要求两组都非空；元素不足两个时回退到唯一可行的分法。
    mode 取 min 表示求最小值，取 max 表示求最大值，其它取值抛 InvalidInput。
    """
    seq = _check_values(values)
    if mode not in ("min", "max"):
        raise InvalidInput("mode 只能是 min 或 max")
    n = len(seq)
    total = sum(seq)
    best = None
    for mask in range(1, (1 << n) - 1):
        left = sum(seq[i] for i in range(n) if mask & (1 << i))
        diff = abs(left - (total - left))
        if best is None or (mode == "min" and diff < best) or (mode == "max" and diff > best):
            best = diff
    if best is None:
        best = abs(seq[0]) if n else 0
    return best
