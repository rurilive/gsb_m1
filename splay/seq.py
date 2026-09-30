"""splay 的现有实现：用一个 Python 列表维护一段整数序列。

当前只有一套最直白的朴素实现。所有操作都直接作用在底层列表上：

    按位置取第 k 个元素        直接下标
    区间翻转 reverse(lo, hi)   截出该段、用切片反序、再拼回原列表
    区间求和 sum(lo, hi)       对截出的子列表逐个累加
    区间赋值 assign(lo, hi,x)  对每个位置逐个写一遍
    区间最小 min(lo, hi)       对截出的子列表逐个比较
    区间最大 max(lo, hi)       对截出的子列表逐个比较

这些做法结果都对，但每次操作都要整段拷贝或逐元素重排，序列一长
就退化成线性甚至平方。这里没有树、没有分层结构，也压不下重复区间
操作的代价。
"""


class Erro(Exception):
    """本工具所有异常的基类。

    调用方可以只捕获 Erro 就把本工具抛出的所有错误一网打尽，
    不必逐个记住具体异常类型的名字。
    """


class IndexErro(Erro):
    """位置或下标非法时抛出。"""


class RangeErro(Erro):
    """区间端点非法时抛出。"""


class ArgErro(Erro):
    """参数类型或取值非法时抛出。"""


class Seq:
    """一段整数序列，用一个 Python 列表直接承载。

    对象一经建立，外观长度由 len(obj) 给出；所有区间操作都在原位
    生效，不返回副本。位置一律从零开始计数。
    """

    def __init__(self, items=None):
        if items is None:
            items = []
        data = []
        for item in items:
            data.append(item)
        self._data = data

    def __len__(self):
        return len(self._data)

    def to_list(self):
        """按当前顺序返回一份浅拷贝的列表，供外部断言与调试。"""
        result = []
        for item in self._data:
            result.append(item)
        return result

    def get(self, pos):
        """取第 pos 个元素，pos 从零开始。"""
        self._check_index(pos)
        return self._data[pos]

    def reverse(self, lo, hi):
        """把区间 [lo, hi) 内的元素顺序整体翻转。"""
        self._check_range(lo, hi)
        if hi - lo <= 1:
            return
        segment = self._data[lo:hi]
        backward = []
        i = len(segment) - 1
        while i >= 0:
            backward.append(segment[i])
            i = i - 1
        self._data[lo:hi] = backward

    def sum(self, lo, hi):
        """求区间 [lo, hi) 内所有元素之和。"""
        self._check_range(lo, hi)
        total = 0
        for i in range(lo, hi):
            total = total + self._data[i]
        return total

    def assign(self, lo, hi, value):
        """把区间 [lo, hi) 内每个位置都写成一个相同的值。"""
        self._check_range(lo, hi)
        for i in range(lo, hi):
            self._data[i] = value

    def min(self, lo, hi):
        """求区间 [lo, hi) 内所有元素的最小值。"""
        self._check_range(lo, hi)
        return self._extreme(lo, hi, "min")

    def max(self, lo, hi):
        """求区间 [lo, hi) 内所有元素的最大值。"""
        self._check_range(lo, hi)
        return self._extreme(lo, hi, "max")

    def _extreme(self, lo, hi, mode):
        best = self._data[lo]
        i = lo + 1
        while i < hi:
            current = self._data[i]
            if mode == "min":
                if current < best:
                    best = current
            else:
                if current > best:
                    best = current
            i = i + 1
        return best

    def _check_index(self, pos):
        if not isinstance(pos, int) or isinstance(pos, bool):
            raise ArgErro("pos must be int")
        if pos < 0 or pos >= len(self._data):
            raise IndexErro("pos out of range")

    def _check_range(self, lo, hi):
        for value in (lo, hi):
            if not isinstance(value, int) or isinstance(value, bool):
                raise ArgErro("range bound must be int")
        if lo < 0 or hi > len(self._data):
            raise RangeErro("range bound out of range")
        if lo > hi:
            raise RangeErro("lo must not exceed hi")
