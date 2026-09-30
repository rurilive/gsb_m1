"""spanx：序列左右边界的朴素实现（改造前的基线，纯标准库）。

四类边界全部用最直白的双向扫描完成：对某个位置，从它出发向左或向右一格一格地看，
谁先满足严格更大的比较、严格更小的比较，就返回谁的下标，一直没有就返回约定值负一。
每日温度、某个元素作为最小值能扩到的最大区间、柱状图每个柱子能扩到的左右边界，也
都是由这套逐位置扫描拼出来的；柱状图最大矩形更是把每根柱子当最矮的那根再向两侧扩。
规模一大就是平方量级，但每一步都照着定义做，结果正确。

约定：

- 某一侧没有满足条件的元素时，四类边界一律返回约定值负一。
- 更大与更小都取严格比较，即必须严格大于或严格小于，相等不算命中。
- 以某元素为最小值的最大区间取的都是严格更小边界，区间开闭按左右两侧命中的下标界定。
- 返回的列表与底层数据无关，调用方改动它不影响内部。
"""

_CONVENTION = -1


class SpanError(Exception):
    """spanx 自己抛出的异常统一派生自这个基类。"""


class EmptyInputError(SpanError):
    """对空序列查询边界：没有位置可查。"""


class InvalidInputError(SpanError):
    """入参不合法：非整数、bool 冒充整数、越界下标、非法口径。"""


def _check_values(values):
    """校验输入序列：可迭代、元素为整数且 bool 不算整数。返回新列表。"""
    try:
        items = list(values)
    except TypeError:
        raise InvalidInputError("values must be an iterable of integers")
    for x in items:
        if isinstance(x, bool) or not isinstance(x, int):
            raise InvalidInputError("values must all be integers")
    return items


def _check_index(values, i):
    """校验下标：必须是整数、bool 不算、且在序列范围内。"""
    if isinstance(i, bool) or not isinstance(i, int):
        raise InvalidInputError("index must be an integer")
    if i < 0 or i >= len(values):
        raise InvalidInputError("index out of range")


def _require_nonempty(values):
    """取一批数据并要求非空；空序列在入口直接拒绝。"""
    data = _check_values(values)
    if not data:
        raise EmptyInputError("cannot query bounds on an empty sequence")
    return data


def first_greater_left(values, i):
    """从位置 i 向左看，返回左侧第一个严格大于它的下标，没有返回负一。"""
    data = _check_values(values)
    _check_index(data, i)
    target = data[i]
    j = i - 1
    while j >= 0:
        if data[j] > target:
            return j
        j -= 1
    return _CONVENTION


def first_greater_right(values, i):
    """从位置 i 向右看，返回右侧第一个严格大于它的下标，没有返回负一。"""
    data = _check_values(values)
    _check_index(data, i)
    target = data[i]
    n = len(data)
    j = i + 1
    while j < n:
        if data[j] > target:
            return j
        j += 1
    return _CONVENTION


def first_smaller_left(values, i):
    """从位置 i 向左看，返回左侧第一个严格小于它的下标，没有返回负一。"""
    data = _check_values(values)
    _check_index(data, i)
    target = data[i]
    j = i - 1
    while j >= 0:
        if data[j] < target:
            return j
        j -= 1
    return _CONVENTION


def first_smaller_right(values, i):
    """从位置 i 向右看，返回右侧第一个严格小于它的下标，没有返回负一。"""
    data = _check_values(values)
    _check_index(data, i)
    target = data[i]
    n = len(data)
    j = i + 1
    while j < n:
        if data[j] < target:
            return j
        j += 1
    return _CONVENTION


def greater_bounds(values):
    """一次求出全部位置左右两侧第一个更大元素，返回成对的下标列表。"""
    data = _require_nonempty(values)
    n = len(data)
    left = [-1] * n
    right = [-1] * n
    for i in range(n):
        target = data[i]
        j = i - 1
        while j >= 0:
            if data[j] > target:
                left[i] = j
                break
            j -= 1
        j = i + 1
        while j < n:
            if data[j] > target:
                right[i] = j
                break
            j += 1
    return left, right


def smaller_bounds(values):
    """一次求出全部位置左右两侧第一个更小元素，返回成对的下标列表。"""
    data = _require_nonempty(values)
    n = len(data)
    left = [-1] * n
    right = [-1] * n
    for i in range(n):
        target = data[i]
        j = i - 1
        while j >= 0:
            if data[j] < target:
                left[i] = j
                break
            j -= 1
        j = i + 1
        while j < n:
            if data[j] < target:
                right[i] = j
                break
            j += 1
    return left, right


def min_range_lengths(values):
    """每个元素作为最小值的最大区间长度：向两侧扩到严格更小处。"""
    data = _require_nonempty(values)
    n = len(data)
    lengths = [0] * n
    for i in range(n):
        target = data[i]
        j = i - 1
        while j >= 0 and data[j] >= target:
            j -= 1
        left = j
        j = i + 1
        while j < n and data[j] >= target:
            j += 1
        right = j
        lengths[i] = right - left - 1
    return lengths


def daily_temperatures(values):
    """每日温度：每个位置向右看，第一个严格更暖的天与它相隔多少天。"""
    data = _require_nonempty(values)
    n = len(data)
    waits = [0] * n
    for i in range(n):
        target = data[i]
        j = i + 1
        while j < n:
            if data[j] > target:
                waits[i] = j - i
                break
            j += 1
    return waits


def histogram_bounds(heights):
    """柱状图每根柱子向左向右能扩到的第一家更矮柱子的下标。"""
    data = _require_nonempty(heights)
    n = len(data)
    left = [-1] * n
    right = [n] * n
    for i in range(n):
        target = data[i]
        j = i - 1
        while j >= 0:
            if data[j] < target:
                left[i] = j
                break
            j -= 1
        j = i + 1
        while j < n:
            if data[j] < target:
                right[i] = j
                break
            j += 1
    return left, right


def largest_rectangle(heights):
    """柱状图中最大矩形面积，逐位置把它当作最矮的那一根再向两侧扩。"""
    data = _check_values(heights)
    n = len(data)
    best = 0
    for i in range(n):
        target = data[i]
        j = i - 1
        while j >= 0 and data[j] >= target:
            j -= 1
        left = j
        j = i + 1
        while j < n and data[j] >= target:
            j += 1
        right = j
        area = target * (right - left - 1)
        if area > best:
            best = area
    return best


def count_naive_visits(values):
    """统计朴素路做一轮左右更大边界查询总共比较多少次。"""
    data = _check_values(values)
    n = len(data)
    total = 0
    for i in range(n):
        target = data[i]
        j = i - 1
        while j >= 0:
            total += 1
            if data[j] > target:
                break
            j -= 1
        j = i + 1
        while j < n:
            total += 1
            if data[j] > target:
                break
            j += 1
    return total
