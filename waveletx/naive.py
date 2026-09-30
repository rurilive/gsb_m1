"""waveletx.naive: 改造前的朴素区间查询工具。

对一个静态整数数组提供四项能力，全部靠整段取出区间或者逐个扫描实现：

- kth_smallest：求区间内第 k 小，取出区间后排序再按下标取值；
- range_rank：求某个值在区间内的排名，统计严格小于它的元素个数；
- count_leq：区间内不超过某个值的元素个数；
- count_equal：区间内某个值出现的次数。

区间口径为左闭右开，即 [lo, hi)，数组下标从零开始，第 k 小的 k 同样从零起算。
朴素做法每次查询都要把区间扫一遍甚至排序一遍，多次查询就成平方以上量级。
"""


class WaveletXError(Exception):
    """waveletx 的业务异常基类。"""


class InvalidRangeError(WaveletXError):
    """查询区间非法。"""


class KthOutOfRangeError(WaveletXError):
    """第 k 小的下标 k 越界。"""


def check_range(size, lo, hi):
    """校验左闭右开区间 [lo, hi) 是否落在 [0, size) 之内。

    合法时返回 (lo, hi)，非法时抛出 InvalidRangeError。
    """
    if not isinstance(lo, int) or not isinstance(hi, int) or isinstance(lo, bool) \
            or isinstance(hi, bool):
        raise InvalidRangeError("区间端点必须是整数")
    if lo < 0 or hi > size or lo > hi:
        raise InvalidRangeError(
            "区间非法: [%d, %d) 超出 [0, %d)" % (lo, hi, size))
    return lo, hi


def _bubble_sort_counted(segment):
    """直白的冒泡排序，逐次比较都计数，返回 (有序列表, 比较次数)。"""
    arr = list(segment)
    comparisons = 0
    n = len(arr)
    for i in range(n - 1):
        swapped = False
        for j in range(n - 1 - i):
            comparisons += 1
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
                swapped = True
        if not swapped:
            break
    return arr, comparisons


def _kth_smallest_counted(values, lo, hi, k):
    size = len(values)
    check_range(size, lo, hi)
    if not isinstance(k, int) or isinstance(k, bool):
        raise KthOutOfRangeError("第 k 小的下标必须是整数")
    if k < 0 or k >= hi - lo:
        raise KthOutOfRangeError(
            "第 k 小的下标 %d 超出区间长度 %d" % (k, hi - lo))
    ordered, comparisons = _bubble_sort_counted(values[lo:hi])
    return ordered[k], comparisons


def _range_rank_counted(values, lo, hi, value):
    size = len(values)
    check_range(size, lo, hi)
    count = 0
    comparisons = 0
    for i in range(lo, hi):
        comparisons += 1
        if values[i] < value:
            count += 1
    return count, comparisons


def _count_leq_counted(values, lo, hi, value):
    size = len(values)
    check_range(size, lo, hi)
    count = 0
    comparisons = 0
    for i in range(lo, hi):
        comparisons += 1
        if values[i] <= value:
            count += 1
    return count, comparisons


def _count_equal_counted(values, lo, hi, value):
    size = len(values)
    check_range(size, lo, hi)
    count = 0
    comparisons = 0
    for i in range(lo, hi):
        comparisons += 1
        if values[i] == value:
            count += 1
    return count, comparisons


# ---- 纯函数入口（不带计数） ----

def kth_smallest(values, lo, hi, k):
    """求区间 [lo, hi) 内第 k 小的元素，k 从零起算。"""
    return _kth_smallest_counted(values, lo, hi, k)[0]


def range_rank(values, lo, hi, value):
    """求 value 在区间 [lo, hi) 内的排名，即严格小于它的元素个数。"""
    return _range_rank_counted(values, lo, hi, value)[0]


def count_leq(values, lo, hi, value):
    """求区间 [lo, hi) 内不超过 value 的元素个数。"""
    return _count_leq_counted(values, lo, hi, value)[0]


def count_equal(values, lo, hi, value):
    """求 value 在区间 [lo, hi) 内出现的次数。"""
    return _count_equal_counted(values, lo, hi, value)[0]


class NaiveRangeIndex:
    """朴素区间查询索引，绑定一个数组并累计比较次数。

    每项查询都把区间整段取出排序或者逐个扫描，因此比较次数随区间长度
    线性甚至平方增长；累计值只反映已经跑过的查询，可读取也可清零。
    """

    def __init__(self, values):
        self._values = list(values)
        self._comparisons = 0

    def __len__(self):
        return len(self._values)

    def values(self):
        """返回内部数组的一份拷贝。"""
        return list(self._values)

    def reset_comparisons(self):
        """把累计比较次数清零。"""
        self._comparisons = 0

    def comparison_count(self):
        """返回累计比较次数。"""
        return self._comparisons

    def kth_smallest(self, lo, hi, k):
        value, comparisons = _kth_smallest_counted(self._values, lo, hi, k)
        self._comparisons += comparisons
        return value

    def range_rank(self, lo, hi, value):
        count, comparisons = _range_rank_counted(
            self._values, lo, hi, value)
        self._comparisons += comparisons
        return count

    def count_leq(self, lo, hi, value):
        count, comparisons = _count_leq_counted(
            self._values, lo, hi, value)
        self._comparisons += comparisons
        return count

    def count_equal(self, lo, hi, value):
        count, comparisons = _count_equal_counted(
            self._values, lo, hi, value)
        self._comparisons += comparisons
        return count
