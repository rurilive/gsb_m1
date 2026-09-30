"""fracprog 的最优比率工具（改造前的现状）。

现在只有一条朴素路：给定若干元素的收益与成本，求子集使收益之和与成本之和的
比值最大，全靠枚举全部选取组合再逐个算比值取极值。组合数随元素数指数上涨。
二分答案加可行性判定、以及动态规划或贪心在特定结构上直接求最优比率这类做法见
任务描述。
"""

from fractions import Fraction


class Erro(Exception):
    """本模块所有对外异常的公共基类。"""


class RatioError(Erro):
    """最优比率工具的参数非法。"""


def _is_int(value):
    """是不是真正的整数，布尔值不算整数。"""
    if isinstance(value, bool):
        return False
    return isinstance(value, int)


def _is_any_int(value):
    """整数或分数都算合法数值，布尔值不算。"""
    if isinstance(value, bool):
        return False
    return isinstance(value, int) or isinstance(value, Fraction)


def to_fraction(value):
    """把整数或分数统一成真分数，布尔与其它类型一律拒绝。"""
    if not _is_any_int(value):
        raise RatioError("value must be an int or Fraction")
    return Fraction(value)


def normalize_items(items):
    """校验并归一元素序列为二元组列表，收益与成本都化成真分数。

    收益与成本必须是整数或分数，可以为负，但两者不允许同时为零以免比值无意义。
    空序列是合法的空集合。
    """
    if items is None:
        raise RatioError("items must not be None")
    try:
        length = len(items)
    except TypeError:
        raise RatioError("items must be a sequence")
    result = []
    for index in range(length):
        item = items[index]
        try:
            profit, cost = item
        except (TypeError, ValueError):
            raise RatioError("each item must be a profit-cost pair")
        profit = to_fraction(profit)
        cost = to_fraction(cost)
        if profit == 0 and cost == 0:
            raise RatioError("profit and cost must not both be zero")
        result.append((profit, cost))
    return result


def _check_k(k):
    """恰好选取的个数必须是非负整数。"""
    if not _is_int(k) or k < 0:
        raise RatioError("k must be a non-negative int")


def _check_ratio(ratio):
    """待判定的比率统一成真分数。"""
    return to_fraction(ratio)


def naive_ratio(profit, cost):
    """由收益之和与成本之和算比值，成本为零时按口径拒绝。

    分母为零表示比值没有有限取值，这里直接报错而不是返回无穷大。
    """
    profit = to_fraction(profit)
    cost = to_fraction(cost)
    if cost == 0:
        raise RatioError("ratio undefined when total cost is zero")
    return profit / cost


def _check_dependency(n, dep):
    """校验依赖表并归一成长度为 n 的列表，第 i 项是元素 i 的前驱下标或 None。

    前驱表示只要选中某元素，就必须同时选中它的前驱；前驱自身可以没有约束。依赖
    关系不允许成环。空依赖等价于没有任何约束。
    """
    if dep is None:
        return [None] * n
    try:
        length = len(dep)
    except TypeError:
        raise RatioError("dependency must be a sequence")
    if length != n:
        raise RatioError("dependency length must match item count")
    result = []
    for index in range(n):
        need = dep[index]
        if need is None:
            result.append(None)
            continue
        if not _is_int(need) or need < 0 or need >= n:
            raise RatioError("dependency entry must be an item index or None")
        if need == index:
            raise RatioError("an item must not depend on itself")
        result.append(need)
    return result


def _is_acyclic(needs):
    """依赖关系不能成环，从每个元素顺着前驱走一遍看有没有回到自己。"""
    n = len(needs)
    for start in range(n):
        seen = set()
        current = start
        while current is not None:
            if current in seen:
                return False
            seen.add(current)
            current = needs[current]
    return True


def _closure_ok(needs, subset):
    """选取方案是否满足依赖：选中元素的整个前驱链都要在选取里。"""
    member = set(subset)
    for index in subset:
        current = needs[index]
        while current is not None:
            if current not in member:
                return False
            current = needs[current]
    return True


def _subsets(n):
    """逐个吐出零到 n 减一的全部下标组合，按位枚举，最直白的老路。"""
    for mask in range(1 << n):
        subset = []
        for index in range(n):
            if mask & (1 << index):
                subset.append(index)
        yield tuple(subset)


def _ratio_of_subset(profits, costs, subset):
    """一个选取方案的比值，成本之和为零时按口径拒绝。"""
    profit = 0
    cost = 0
    for index in subset:
        profit += profits[index]
        cost += costs[index]
    if cost == 0:
        raise RatioError("ratio undefined when total cost is zero")
    return profit / cost


def _pick_best(profits, costs, n, accept):
    """枚举全部组合，在满足 accept 的非空组合里取比值最大者。

    比值并列时取下标序列字典序最小的方案。空集合按约定给出零比值与空方案。
    """
    count = 0
    best_key = None
    best_ratio = None
    best_subset = None
    for subset in _subsets(n):
        count += 1
        if not subset:
            continue
        if not accept(subset):
            continue
        ratio = _ratio_of_subset(profits, costs, subset)
        key = (-ratio, list(subset))
        if best_key is None or key < best_key:
            best_key = key
            best_ratio = ratio
            best_subset = list(subset)
    if best_subset is None:
        return {"ratio": Fraction(0), "selection": [], "count": count}
    return {"ratio": best_ratio, "selection": best_subset, "count": count}


def _split(items):
    """把元素序列拆成收益与成本两串真分数。"""
    pairs = normalize_items(items)
    return pairs, [pair[0] for pair in pairs], [pair[1] for pair in pairs]


def best_selection(items):
    """求使收益之和与成本之和之比最大的选取方案，枚举全部组合取极值。

    返回比值的精确分数、取得最优的选取方案与累计枚举的组合次数；比值并列时按下
    标序列字典序最小取定。空集合按约定返回零比值与空方案。
    """
    pairs, profits, costs = _split(items)
    return _pick_best(profits, costs, len(pairs), lambda subset: True)


def best_selection_k(items, k):
    """求恰好选取 k 个元素时的最优比率，枚举全部组合后只留大小为 k 的。

    k 大于元素数属于非法参数，这里直接报错；k 为零时返回零比值与空方案。
    """
    pairs, profits, costs = _split(items)
    _check_k(k)
    n = len(pairs)
    if k > n:
        raise RatioError("k larger than item count")
    if k == 0:
        total = sum(1 for _ in _subsets(n))
        return {"ratio": Fraction(0), "selection": [], "count": total}
    return _pick_best(profits, costs, n, lambda subset: len(subset) == k)


def best_selection_with_deps(items, dep):
    """求满足依赖约束时的最优比率，枚举组合后逐个检查前驱链再取极值。

    依赖表长度为元素数，第 i 项是元素 i 的前驱下标或 None；选中元素必须同时选中
    它的整个前驱链。依赖成环或越界属于非法参数。空集总满足约束。
    """
    pairs, profits, costs = _split(items)
    n = len(pairs)
    needs = _check_dependency(n, dep)
    if not _is_acyclic(needs):
        raise RatioError("dependency must be acyclic")
    return _pick_best(profits, costs, n,
                      lambda subset: _closure_ok(needs, subset))


def is_reachable(items, target):
    """判断给定比率是否可达，枚举全部组合看有没有一个组合的比值不低于它。"""
    pairs, profits, costs = _split(items)
    target = _check_ratio(target)
    n = len(pairs)
    count = 0
    for subset in _subsets(n):
        count += 1
        if not subset:
            continue
        ratio = _ratio_of_subset(profits, costs, subset)
        if ratio >= target:
            return {"reachable": True, "count": count}
    return {"reachable": False, "count": count}


def combination_count(n):
    """n 个元素的全部选取组合总数，也就是朴素枚举要过一遍的候选数。"""
    if not _is_int(n) or n < 0:
        raise RatioError("n must be a non-negative int")
    return 1 << n


class Tool:
    """绑定一批元素的比率工具，只有枚举组合这一条路。

    求最优比率、求取得最优的选取方案、判断比率是否可达、求恰好 k 个的最优、求带
    依赖的选取最优都提供方法，并累计枚举组合的次数，供与二分判定次数对照规模。
    """

    def __init__(self, items):
        self._pairs = normalize_items(items)
        self._count = 0

    def reset_count(self):
        """把枚举组合计数清零。"""
        self._count = 0

    def enumeration_count(self):
        """自上次清零以来累计枚举了多少个候选组合。"""
        return self._count

    def best_selection(self):
        """朴素求最优比率与选取方案，枚举全部组合，计数随元素数指数上涨。"""
        result = best_selection(self._pairs)
        self._count += result["count"]
        return {"ratio": result["ratio"], "selection": result["selection"]}

    def best_selection_k(self, k):
        """朴素求恰好 k 个的最优比率，同样枚举全部组合。"""
        result = best_selection_k(self._pairs, k)
        self._count += result["count"]
        return {"ratio": result["ratio"], "selection": result["selection"]}

    def best_selection_with_deps(self, dep):
        """朴素求带依赖的选取最优，同样枚举全部组合。"""
        result = best_selection_with_deps(self._pairs, dep)
        self._count += result["count"]
        return {"ratio": result["ratio"], "selection": result["selection"]}

    def is_reachable(self, target):
        """朴素判断比率是否可达，枚举全部组合。"""
        result = is_reachable(self._pairs, target)
        self._count += result["count"]
        return result["reachable"]
