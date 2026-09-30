"""treap 的现有实现：用一个 Python 列表维护一段整数序列。

当前只有一套最直白的朴素实现。所有操作都直接作用在底层列表上：

    按位置取第 pos 个元素       直接下标
    按位置插入 insert(pos, v)   取前段、接单个元素、再接后段，整段拼回
    按位置删除 remove(pos)      取前段与后段，跳过被删位置，整段拼回
    区间求和 sum(lo, hi)        对截出的子列表逐个累加
    区间最小 min(lo, hi)        对截出的子列表逐个比较
    区间最大 max(lo, hi)        对截出的子列表逐个比较
    区间第 k 小 kth(lo, hi, k)  截出该段自行排序后按下标取
    按排名找元素 rank(pos)      取该位置的值，再从头逐个数比它小的个数

这些做法结果都对，但每次操作都要整段拷贝或逐元素重排，序列一长
就退化成线性甚至平方。这里没有树、没有分层结构，也压不下重复按
位置插删与区间查询的代价。
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

    对象一经建立，外观长度由 len(obj) 给出；所有按位置的操作都在
    原位生效，不返回副本。位置一律从零开始计数。
    """

    def __init__(self, items=None):
        if items is None:
            items = []
        data = []
        for item in items:
            self._check_value(item)
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

    def insert(self, pos, value):
        """在第 pos 个元素之前插入 value，pos 等于当前长度表示追加到末尾。"""
        self._check_insert_index(pos)
        self._check_value(value)
        self._data[pos:pos] = [value]

    def remove(self, pos):
        """删除第 pos 个元素，并把它返回。"""
        self._check_index(pos)
        value = self._data[pos]
        head = self._data[:pos]
        tail = self._data[pos + 1:]
        self._data = head + tail
        return value

    def sum(self, lo, hi):
        """求区间 [lo, hi) 内所有元素之和。"""
        self._check_range(lo, hi)
        total = 0
        for i in range(lo, hi):
            total = total + self._data[i]
        return total

    def min(self, lo, hi):
        """求区间 [lo, hi) 内所有元素的最小值，空区间按约定返回 0。"""
        self._check_range(lo, hi)
        if lo == hi:
            return 0
        return self._extreme(lo, hi, "min")

    def max(self, lo, hi):
        """求区间 [lo, hi) 内所有元素的最大值，空区间按约定返回 0。"""
        self._check_range(lo, hi)
        if lo == hi:
            return 0
        return self._extreme(lo, hi, "max")

    def kth(self, lo, hi, k):
        """求区间 [lo, hi) 内第 k 小的元素，k 从零开始。

        重复值按占有独立名次处理，第零小即最小。返回该值。
        """
        self._check_range(lo, hi)
        if not isinstance(k, int) or isinstance(k, bool):
            raise ArgErro("k must be int")
        if k < 0 or k >= hi - lo:
            raise RangeErro("k out of range")
        segment = []
        for i in range(lo, hi):
            segment.append(self._data[i])
        segment.sort()
        return segment[k]

    def rank(self, pos):
        """数一数整个序列里比第 pos 个元素小的元素有几个，返回这个个数。

        重复值不互相计数，相同值的名次一致。
        """
        self._check_index(pos)
        probe = self._data[pos]
        count = 0
        for i in range(len(self._data)):
            if self._data[i] < probe:
                count = count + 1
        return count

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

    def _check_value(self, value):
        if not isinstance(value, int) or isinstance(value, bool):
            raise ArgErro("value must be int")

    def _check_index(self, pos):
        if not isinstance(pos, int) or isinstance(pos, bool):
            raise ArgErro("pos must be int")
        if pos < 0 or pos >= len(self._data):
            raise IndexErro("pos out of range")

    def _check_insert_index(self, pos):
        if not isinstance(pos, int) or isinstance(pos, bool):
            raise ArgErro("pos must be int")
        if pos < 0 or pos > len(self._data):
            raise IndexErro("pos out of range")

    def _check_range(self, lo, hi):
        for value in (lo, hi):
            if not isinstance(value, int) or isinstance(value, bool):
                raise ArgErro("range bound must be int")
        if lo < 0 or hi > len(self._data):
            raise RangeErro("range bound out of range")
        if lo > hi:
            raise RangeErro("lo must not exceed hi")
