"""定长滑动窗口上的统计聚合，当前为改造前的朴素基线。

朴素口径：给定一个序列与窗口大小，对每个窗口从头把窗口内的元素重新扫一遍，
逐个求最大、最小、排序取中位、累加求和、去重计数。窗口一滑就整段重算，
不做任何增量维护，也没有单调队列与有序结构。行为正确但重复劳动多。
"""


class WinxError(ValueError):
    """窗口工具集中所有参数错误的基类。"""


class InvalidWindowSizeError(WinxError):
    """窗口大小不是正整数。"""


class InvalidSequenceError(WinxError):
    """输入序列不是可迭代的数值序列。"""


def _as_list(seq):
    """把输入序列拷成列表，非序列输入按包内异常拒绝。"""
    try:
        items = list(seq)
    except TypeError:
        raise InvalidSequenceError("sequence must be an iterable of numbers")
    return items


def _check_window_size(window_size):
    """窗口大小必须是正整数，否则快速失败。"""
    if isinstance(window_size, bool) or not isinstance(window_size, int):
        raise InvalidWindowSizeError("window size must be a positive integer")
    if window_size <= 0:
        raise InvalidWindowSizeError("window size must be a positive integer")
    return window_size


def _window_bounds(length, window_size):
    """枚举所有窗口的起止下标；窗口大于序列长时不产生任何窗口。"""
    if window_size > length:
        return []
    return [(start, start + window_size) for start in range(length - window_size + 1)]


class WindowStats:
    """定长窗口上的朴素统计器，每个窗口独立重扫，是流式窗口工具集改造前的基线。"""

    def __init__(self, window_size):
        self.window_size = _check_window_size(window_size)

    def _slice(self, values, start, end):
        return values[start:end]

    def maxima(self, seq):
        """每个窗口的最大值序列，逐窗口线性扫描取得。"""
        values = _as_list(seq)
        out = []
        for start, end in _window_bounds(len(values), self.window_size):
            chunk = self._slice(values, start, end)
            out.append(max(chunk))
        return out

    def minima(self, seq):
        """每个窗口的最小值序列，逐窗口线性扫描取得。"""
        values = _as_list(seq)
        out = []
        for start, end in _window_bounds(len(values), self.window_size):
            chunk = self._slice(values, start, end)
            out.append(min(chunk))
        return out

    def medians(self, seq):
        """每个窗口的中位数序列；偶数窗口取中间两个的算术平均。"""
        values = _as_list(seq)
        out = []
        for start, end in _window_bounds(len(values), self.window_size):
            chunk = sorted(self._slice(values, start, end))
            n = len(chunk)
            mid = n // 2
            if n % 2 == 1:
                out.append(float(chunk[mid]))
            else:
                out.append((chunk[mid - 1] + chunk[mid]) / 2.0)
        return out

    def sums(self, seq):
        """每个窗口的元素和序列，逐窗口累加取得。"""
        values = _as_list(seq)
        out = []
        for start, end in _window_bounds(len(values), self.window_size):
            chunk = self._slice(values, start, end)
            out.append(float(sum(chunk)))
        return out

    def distinct_counts(self, seq):
        """每个窗口内不同元素个数序列，逐窗口去重计数取得。"""
        values = _as_list(seq)
        out = []
        for start, end in _window_bounds(len(values), self.window_size):
            chunk = self._slice(values, start, end)
            out.append(len(set(chunk)))
        return out

    def kth_smallest(self, seq, k):
        """每个窗口内第k小的元素序列，k从0起算，逐窗口排序后取位。"""
        if isinstance(k, bool) or not isinstance(k, int):
            raise WinxError("k must be an integer index")
        if k < 0 or k >= self.window_size:
            raise WinxError("k out of range for the window size")
        values = _as_list(seq)
        out = []
        for start, end in _window_bounds(len(values), self.window_size):
            chunk = sorted(self._slice(values, start, end))
            out.append(chunk[k])
        return out

    def rank(self, seq, value):
        """每个窗口内小于该值的元素个数序列，逐窗口比对计数取得。"""
        values = _as_list(seq)
        out = []
        for start, end in _window_bounds(len(values), self.window_size):
            chunk = self._slice(values, start, end)
            out.append(sum(1 for item in chunk if item < value))
        return out


def window_max(seq, window_size):
    """便捷函数：朴素口径下求每个窗口的最大值序列。"""
    return WindowStats(window_size).maxima(seq)


def window_min(seq, window_size):
    """便捷函数：朴素口径下求每个窗口的最小值序列。"""
    return WindowStats(window_size).minima(seq)


def window_median(seq, window_size):
    """便捷函数：朴素口径下求每个窗口的中位数序列。"""
    return WindowStats(window_size).medians(seq)


def window_sum(seq, window_size):
    """便捷函数：朴素口径下求每个窗口的和序列。"""
    return WindowStats(window_size).sums(seq)


def window_distinct(seq, window_size):
    """便捷函数：朴素口径下求每个窗口的不同元素个数序列。"""
    return WindowStats(window_size).distinct_counts(seq)


def window_kth(seq, window_size, k):
    """便捷函数：朴素口径下求每个窗口内第k小的元素序列。"""
    return WindowStats(window_size).kth_smallest(seq, k)


def window_rank(seq, window_size, value):
    """便捷函数：朴素口径下求每个窗口内小于该值的元素个数序列。"""
    return WindowStats(window_size).rank(seq, value)
