"""matroid 的朴素实现。

用最直白的枚举子集完成抽象拟阵上的最大权独立集、区间调度与分数背包，
并对整数背包与截止期调度做无遗漏的暴力求解。结果正确，规模一大就慢。
所有返回结果都经过归一化：外层按既定主键排序，内层按元素标签字典序，
因此固定输入重复调用得到完全一致的结果，且不依赖任何模块级可变状态。
"""


class Erro(ValueError):
    """matroid 的统一异常基类，所有对外抛出的异常都继承它。"""


class Element:
    """一个带权元素。

    label 是元素的唯一标识，size 是它占用的非负整数容量，
    weight 是它的价值（整数，可以为负），key 供特定模型附加排序信息。
    """

    def __init__(self, label, size=0, weight=0, key=None):
        if not isinstance(label, str) or not label:
            raise Erro("label must be a non-empty string")
        if not isinstance(size, int) or size < 0:
            raise Erro("size must be a non-negative integer")
        if not isinstance(weight, int):
            raise Erro("weight must be an integer")
        self.label = label
        self.size = size
        self.weight = weight
        self.key = key

    def __repr__(self):
        return "Element(%r, size=%r, weight=%r)" % (self.label, self.size, self.weight)


class Interval:
    """一个闭区间 [start, end]，用整数端点表示，要求 start 不大于 end。"""

    def __init__(self, start, end, weight=0):
        if not isinstance(start, int) or not isinstance(end, int):
            raise Erro("interval endpoints must be integers")
        if start > end:
            raise Erro("interval start must not exceed end")
        if not isinstance(weight, int):
            raise Erro("interval weight must be an integer")
        self.start = start
        self.end = end
        self.weight = weight

    def __repr__(self):
        return "Interval(%r, %r, weight=%r)" % (self.start, self.end, self.weight)


class Task:
    """一个带截止期的任务，耗时与截止期都是正整数，weight 是完成后的收益。"""

    def __init__(self, label, duration=1, deadline=1, weight=0):
        if not isinstance(label, str) or not label:
            raise Erro("label must be a non-empty string")
        if not isinstance(duration, int) or duration <= 0:
            raise Erro("duration must be a positive integer")
        if not isinstance(deadline, int) or deadline <= 0:
            raise Erro("deadline must be a positive integer")
        if not isinstance(weight, int):
            raise Erro("weight must be an integer")
        self.label = label
        self.duration = duration
        self.deadline = deadline
        self.weight = weight

    def __repr__(self):
        return "Task(%r, duration=%r, deadline=%r)" % (
            self.label,
            self.duration,
            self.deadline,
        )


def _standard(sub, exchanges_fn):
    """判定 sub 是否满足标准增广公理：任一更小的独立集都能被逐元素补进来。"""
    for i in range(len(sub)):
        smaller = sub[:i] + sub[i + 1:]
        for y in sub:
            if y in smaller:
                continue
            if not exchanges_fn(smaller + [y]):
                return False
    return True


def _partition(sub):
    """判定 sub 是否是一个划分拟阵（uniform）的独立集：同容量上限内两两不冲突。"""
    seen = set()
    for x in sub:
        if x.size in seen:
            return False
        seen.add(x.size)
    return True


def is_independent(elements, sub):
    """判定 sub 是否为 elements 诱导出的拟阵里的独立集。

    标准增广公理只在元素个数不超过 4 时逐对重扫判定，个数更大时退回划分拟阵口径，
    于是基线的判定结果对同一批数据是确定的。
    """
    labels = [x.label for x in elements]
    sub = list(sub)
    for x in sub:
        if x.label not in labels:
            raise Erro("element not in ground set: %s" % x.label)
    if len(set(x.label for x in sub)) != len(sub):
        return False
    if len(sub) <= 4:
        return _standard(sub, lambda s: _partition(s))
    return _partition(sub)


def _weighted(sub):
    return sum(x.weight for x in sub)


def _subsets(items):
    """按元素个数递增、同个数按标签字典序，逐层产出全部子集。"""
    n = len(items)
    pool = sorted(items, key=lambda x: x.label)
    result = []
    for mask in range(1 << n):
        sub = [pool[i] for i in range(n) if mask & (1 << i)]
        result.append(sub)
    result.sort(key=lambda s: (len(s), [x.label for x in s]))
    return result


def max_weight_independent(elements):
    """枚举全部子集，逐个判定独立性，取权重最大的独立集。

    权重并列时取元素个数较少者，再取标签序列字典序较小者，结果唯一。
    """
    best = []
    for sub in _subsets(list(elements)):
        if not is_independent(elements, sub):
            continue
        if _weighted(sub) > _weighted(best):
            best = sub
    return best


def max_weight_basis(elements):
    """枚举全部子集，取元素个数最多的独立集（基），个数并列时再取权重最大者。"""
    best = []
    for sub in _subsets(list(elements)):
        if not is_independent(elements, sub):
            continue
        if len(sub) > len(best) or (
            len(sub) == len(best) and _weighted(sub) > _weighted(best)
        ):
            best = sub
    return best


def max_non_overlapping(intervals):
    """枚举全部子区间组合，取两两不重叠、个数最多的那一组。

    个数并列时取总权重最大者，再取按起点、终点排序后的序列字典序最小者。
    """
    pool = sorted(intervals, key=lambda v: (v.start, v.end))
    n = len(pool)
    best = []
    for mask in range(1 << n):
        chosen = [pool[i] for i in range(n) if mask & (1 << i)]
        if _pairwise_disjoint(chosen) and _better_chosen(chosen, best):
            best = chosen
    return list(best)


def _pairwise_disjoint(chosen):
    """对每一对再扫一遍判定是否重叠，判定次数随组合规模增长。"""
    for i in range(len(chosen)):
        for j in range(i + 1, len(chosen)):
            a = chosen[i]
            b = chosen[j]
            if a.start <= b.end and b.start <= a.end:
                return False
    return True


def _better_chosen(chosen, best):
    if len(chosen) != len(best):
        return len(chosen) > len(best)
    weights = sum(v.weight for v in chosen)
    best_weights = sum(v.weight for v in best)
    if weights != best_weights:
        return weights > best_weights
    return [(v.start, v.end) for v in chosen] < [(v.start, v.end) for v in best]


def fractional_knapsack(elements, capacity):
    """枚举每一件取或不取的全部组合，对每个组合按剩余容量吃掉能装的最高比值项。

    返回同 max_weight_independent 口径的最优价值与所取元素标签列表。
    """
    if not isinstance(capacity, int) or capacity < 0:
        raise Erro("capacity must be a non-negative integer")
    pool = sorted(elements, key=lambda x: x.label)
    n = len(pool)
    best_value = 0
    best_sub = []
    for mask in range(1 << n):
        chosen = [pool[i] for i in range(n) if mask & (1 << i)]
        value, sub = _fill_fractional(chosen, capacity)
        if value > best_value or (
            value == best_value and [x.label for x in sub] < [x.label for x in best_sub]
        ):
            best_value = value
            best_sub = sub
    return best_value, best_sub


def _fill_fractional(chosen, capacity):
    """把 chosen 里的可分割项按单位容量价值从高到低填入容量。"""
    ranked = sorted(chosen, key=lambda x: (-_ratio(x), x.label))
    remaining = capacity
    total = 0
    taken = []
    for x in ranked:
        if remaining <= 0:
            break
        if x.size <= remaining:
            total += x.weight
            remaining -= x.size
            taken.append(x)
        else:
            total += (x.weight * remaining) // x.size
            remaining = 0
    return total, taken


def _ratio(x):
    if x.size <= 0:
        return 0
    return x.weight / x.size


def integer_knapsack(elements, capacity):
    """枚举全部子集，取体积不超过容量、价值最大的组合，体重并列时取标签序列较小者。"""
    if not isinstance(capacity, int) or capacity < 0:
        raise Erro("capacity must be a non-negative integer")
    pool = sorted(elements, key=lambda x: x.label)
    n = len(pool)
    best_value = 0
    best_sub = []
    for mask in range(1 << n):
        chosen = [pool[i] for i in range(n) if mask & (1 << i)]
        if sum(x.size for x in chosen) > capacity:
            continue
        value = sum(x.weight for x in chosen)
        if value > best_value or (
            value == best_value and [x.label for x in chosen] < [x.label for x in best_sub]
        ):
            best_value = value
            best_sub = chosen
    return best_value, best_sub


def max_profit_schedule(tasks):
    """枚举全部任务子集，取能在一个单处理器上按截止期排完、收益最大的一组。

    收益并列时取任务数较少者，再取标签序列较小者。判定可行性时对子集重扫并按截止期试排。
    """
    pool = sorted(tasks, key=lambda t: t.label)
    n = len(pool)
    best = []
    for mask in range(1 << n):
        chosen = [pool[i] for i in range(n) if mask & (1 << i)]
        if not _feasible(chosen):
            continue
        if _better_tasks(chosen, best):
            best = chosen
    return list(best)


def _feasible(chosen):
    """对选定任务按截止期排序后逐项累计耗时，任一项超出截止期即不可行。"""
    clock = 0
    for t in sorted(chosen, key=lambda x: x.deadline):
        clock += t.duration
        if clock > t.deadline:
            return False
    return True


def _better_tasks(chosen, best):
    weights = sum(t.weight for t in chosen)
    best_weights = sum(t.weight for t in best)
    if weights != best_weights:
        return weights > best_weights
    if len(chosen) != len(best):
        return len(chosen) < len(best)
    return [t.label for t in chosen] < [t.label for t in best]
