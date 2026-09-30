"""seqx 的序列核心：区间操作的朴素（基线）实现。

本模块当前只提供直白的能力，所有算法都落在内部那份平铺列表上：

    - 按下标插入用切片拼接把原位之后的一整段整体后移；
    - 按下标删除用切片把目标位置之后的一整段整体前移；
    - 区间翻转用切片取出那一段、逆序之后再拼回原位；
    - 区间加用循环对区间里的每个元素逐个改写。

这些做法朴素但正确，代价随区间长度或元素个数线性上涨，中间没有任何
可以复用的层级结构。它们同时是包内其余部分与测试所依赖的现状，必须
保持正确且确定，改造时不许删除，要留下来做对照。
"""


class SeqError(Exception):
    """本包所有异常的基类，调用方捕获它就能兜住全部失败。"""


class IndexOutOfRangeError(SeqError):
    """下标越界：负数下标或下标不小于当前长度。"""


class EmptySequenceError(SeqError):
    """对空序列做了需要元素的取值或统计操作。"""


class InvalidRangeError(SeqError):
    """区间端点不合法，或区间方向与要求不符。"""


class ValueRangeError(SeqError):
    """元素不是整数、或两个序列长度对不上等取值层面的问题。"""


class Seq:
    """基于平铺列表的可变序列，支持按下标与区间的若干操作。

    构造时接收一个整数序列的初值（缺省为空序列），元素允许为负数，
    内部始终按构造给出的顺序保存。所有下标都是零基的，区间一律为
    左闭右开的半开区间。
    """

    def __init__(self, values=None):
        if values is None:
            values = []
        try:
            data = list(values)
        except TypeError:
            raise ValueRangeError("初值必须是可迭代的整数序列")
        for value in data:
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueRangeError("序列元素必须是整数")
        self._data = [int(v) for v in data]

    # -- 基本查询 ------------------------------------------------------

    def __len__(self):
        """返回当前元素个数。"""
        return len(self._data)

    def is_empty(self):
        """序列是否为空。"""
        return not self._data

    def to_list(self):
        """返回内部元素的副本，改动副本不影响序列。"""
        return list(self._data)

    def get(self, index):
        """返回下标处的元素，越界抛 IndexOutOfRangeError。"""
        self._check_index(index)
        return self._data[index]

    def set(self, index, value):
        """把下标处的元素改成给定值，越界抛 IndexOutOfRangeError。"""
        self._check_index(index)
        self._check_value(value)
        self._data[index] = int(value)

    # -- 增删 ----------------------------------------------------------

    def insert(self, index, value):
        """在下标之前插入一个元素。

        下标允许等于当前长度，表示追加到末尾；其余越界情形抛
        IndexOutOfRangeError。朴素实现里这一步会把下标之后的一整段
        元素整体后移。
        """
        self._check_position(index)
        self._check_value(value)
        self._data[index:index] = [int(value)]

    def delete(self, index):
        """删除并返回下标处的元素，越界抛 IndexOutOfRangeError。"""
        self._check_index(index)
        value = self._data[index]
        del self._data[index]
        return value

    # -- 区间操作 ------------------------------------------------------

    def reverse(self, left, right):
        """就地把半开区间 [left, right) 逆序。"""
        self._check_range(left, right)
        self._data[left:right] = self._data[left:right][::-1]

    def add(self, left, right, delta):
        """就地把半开区间 [left, right) 内的每个元素加上 delta。"""
        self._check_range(left, right)
        self._check_value(delta)
        for i in range(left, right):
            self._data[i] += delta

    def sum(self, left, right):
        """返回半开区间 [left, right) 内所有元素之和，空区间为 0。"""
        self._check_range(left, right)
        total = 0
        for i in range(left, right):
            total += self._data[i]
        return total

    def min(self, left, right):
        """返回半开区间 [left, right) 内的最小值，空区间抛 EmptySequenceError。"""
        self._check_range(left, right)
        if left >= right:
            raise EmptySequenceError("空区间没有最小值")
        best = self._data[left]
        for i in range(left + 1, right):
            if self._data[i] < best:
                best = self._data[i]
        return best

    def max(self, left, right):
        """返回半开区间 [left, right) 内的最大值，空区间抛 EmptySequenceError。"""
        self._check_range(left, right)
        if left >= right:
            raise EmptySequenceError("空区间没有最大值")
        best = self._data[left]
        for i in range(left + 1, right):
            if self._data[i] > best:
                best = self._data[i]
        return best

    # -- 校验 ----------------------------------------------------------

    def _check_value(self, value):
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueRangeError("元素必须是整数")

    def _check_index(self, index):
        if not isinstance(index, int) or isinstance(index, bool):
            raise IndexOutOfRangeError("下标必须是整数")
        if index < 0 or index >= len(self._data):
            raise IndexOutOfRangeError(f"下标越界：{index}")

    def _check_position(self, index):
        if not isinstance(index, int) or isinstance(index, bool):
            raise IndexOutOfRangeError("下标必须是整数")
        if index < 0 or index > len(self._data):
            raise IndexOutOfRangeError(f"插入位置越界：{index}")

    def _check_range(self, left, right):
        if not isinstance(left, int) or isinstance(left, bool):
            raise InvalidRangeError("左端点必须是整数")
        if not isinstance(right, int) or isinstance(right, bool):
            raise InvalidRangeError("右端点必须是整数")
        if left < 0 or right < 0 or left > len(self._data) or right > len(self._data):
            raise InvalidRangeError(f"区间越界：[{left}, {right})")
        if left > right:
            raise InvalidRangeError(f"区间方向不合法：[{left}, {right})")


def replay(values, operations):
    """把一串操作依次作用在给定初值上，返回序列与逐次结果快照。

    每个操作是一个元组，第一项是操作名，其余是参数，支持的名字与
    Seq 上的方法同名：insert、delete、reverse、add、sum、min、max、
    get、set。返回一个二元组，第一项是结束时的元素列表，第二项是
    每次操作返回结果的列表。这是给对照与自检用的便捷入口。
    """
    seq = Seq(values)
    results = []
    for operation in operations:
        name = operation[0]
        args = operation[1:]
        results.append(getattr(seq, name)(*args))
    return seq.to_list(), results
