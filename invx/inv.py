"""invx 的基线朴素实现。

现状：逆序对、正序对与相等对一律用双重循环枚举所有下标对来数；
重复判定、不同取值计数、按排名取值、求排名一律先排序再做一次线性扫描。
结果正确，规模一大代价就随元素个数平方或排序全额上涨。
"""


class InversionError(Exception):
    """本包全部自定义异常的基类。"""


class InvalidInputError(InversionError):
    """输入不是可接受的整数序列时抛出。"""


class EmptySequenceError(InversionError):
    """要求非空序列却不满足时抛出。"""


class SequenceTooShortError(InversionError):
    """序列长度不足以回答所问的排名或取值时抛出。"""


def _as_list(values):
    """把输入规整成一份新的整数列表，非法输入当场失败。"""
    if isinstance(values, (str, bytes)) or not hasattr(values, "__iter__"):
        raise InvalidInputError("需要一个可迭代的整数序列")
    out = []
    for item in values:
        if isinstance(item, bool) or not isinstance(item, int):
            raise InvalidInputError("序列里出现了非整数元素")
        out.append(item)
    return out


def count_inversions(values):
    """数严格逆序对：靠前元素严格大于靠后元素的下标对个数。

    朴素做法：双重循环枚举所有下标对逐一比较。
    """
    data = _as_list(values)
    total = 0
    for i in range(len(data)):
        for j in range(i + 1, len(data)):
            if data[i] > data[j]:
                total += 1
    return total


def count_ordered_pairs(values):
    """数严格正序对：靠前元素严格小于靠后元素的下标对个数。

    朴素做法：双重循环枚举所有下标对逐一比较。
    """
    data = _as_list(values)
    total = 0
    for i in range(len(data)):
        for j in range(i + 1, len(data)):
            if data[i] < data[j]:
                total += 1
    return total


def count_equal_pairs(values):
    """数相等对：靠前元素与靠后元素恰好相等的下标对个数。

    朴素做法：双重循环枚举所有下标对逐一比较。
    """
    data = _as_list(values)
    total = 0
    for i in range(len(data)):
        for j in range(i + 1, len(data)):
            if data[i] == data[j]:
                total += 1
    return total


def total_pairs(values):
    """下标对总数，等于长度选二。"""
    data = _as_list(values)
    n = len(data)
    return n * (n - 1) // 2


def max_inversions(n):
    """长度为 n 的序列最多能有几个逆序对（严格递降时取到）。"""
    if isinstance(n, bool) or not isinstance(n, int):
        raise InvalidInputError("长度必须是整数")
    if n < 0:
        raise InvalidInputError("长度不能为负")
    return n * (n - 1) // 2


def has_duplicates(values):
    """序列里是否存在重复取值。

    朴素做法：排序之后线性扫一遍，看相邻两个是否相等。
    """
    data = sorted(_as_list(values))
    for i in range(1, len(data)):
        if data[i] == data[i - 1]:
            return True
    return False


def distinct_count(values):
    """序列里不同取值的个数。

    朴素做法：排序之后线性扫一遍，数出取值发生变化的次数再加一。
    """
    data = sorted(_as_list(values))
    if not data:
        return 0
    count = 1
    for i in range(1, len(data)):
        if data[i] != data[i - 1]:
            count += 1
    return count


def kth_smallest(values, k):
    """返回第 k 小（k 从 1 开始）的元素，越界抛错。

    朴素做法：整体排序之后直接按下标取。
    """
    data = sorted(_as_list(values))
    if not data:
        raise EmptySequenceError("空序列没有第几小")
    if isinstance(k, bool) or not isinstance(k, int) or k < 1 or k > len(data):
        raise SequenceTooShortError("排名超出序列长度")
    return data[k - 1]


def rank_of(values, x):
    """返回严格小于 x 的元素个数。"""
    data = sorted(_as_list(values))
    count = 0
    for item in data:
        if item < x:
            count += 1
        else:
            break
    return count


class Values:
    """把一条整数序列包成一个可反复查询的统计器。"""

    def __init__(self, values=()):
        self._data = _as_list(values)

    def to_list(self):
        return list(self._data)

    def __len__(self):
        return len(self._data)

    def is_empty(self):
        return not self._data

    def count_inversions(self):
        return count_inversions(self._data)

    def count_ordered_pairs(self):
        return count_ordered_pairs(self._data)

    def count_equal_pairs(self):
        return count_equal_pairs(self._data)

    def total_pairs(self):
        return total_pairs(self._data)

    def has_duplicates(self):
        return has_duplicates(self._data)

    def distinct_count(self):
        return distinct_count(self._data)

    def kth_smallest(self, k):
        return kth_smallest(self._data, k)

    def rank_of(self, x):
        return rank_of(self._data, x)

    def summary(self):
        """一份固定的统计摘要，键的顺序写死，便于逐项对照。"""
        return {
            "length": len(self._data),
            "inversions": self.count_inversions(),
            "ordered": self.count_ordered_pairs(),
            "equal": self.count_equal_pairs(),
            "distinct": self.distinct_count(),
            "has_duplicates": self.has_duplicates(),
        }
