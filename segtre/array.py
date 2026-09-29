"""segtre 的朴素逐元素区间求和实现（改造前的现状）。

现在只有一条路：区间查询就是把区间里的元素挨个拿出来累加，值变更就是
把下标处的元素直接改掉。没有建树，没有区间最值，没有点更新与区间更新的
区分，没有懒惰传播，没有可配置的合并函数，也没有按前缀和二分的定位。
线段树、懒惰传播与多种聚合见任务描述。
"""


class SegArray:
    """一串整数，区间求和只有逐元素累加这一种做法。"""

    def __init__(self, values=()):
        """用一串整数初始化，返回这些值的独立副本。"""
        vals = list(values)
        for v in vals:
            if not isinstance(v, int) or isinstance(v, bool):
                raise ValueError("values must be ints")
        self._data = vals

    def __len__(self):
        """返回元素个数。"""
        return len(self._data)

    def __getitem__(self, index):
        """按下标取回单个元素。"""
        return self._data[index]

    def to_list(self):
        """返回当前底层数据的一份副本。"""
        return list(self._data)

    def set_value(self, index, value):
        """把下标 index 处的元素直接改成 value，返回旧值。"""
        self._check_index(index)
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError("value must be an int")
        old = self._data[index]
        self._data[index] = value
        return old

    def add_value(self, index, delta):
        """把下标 index 处的元素加上 delta，返回加完之后的新值。"""
        self._check_index(index)
        if not isinstance(delta, int) or isinstance(delta, bool):
            raise ValueError("delta must be an int")
        self._data[index] += delta
        return self._data[index]

    def range_sum(self, left, right):
        """返回半开区间 [left, right) 的和，空区间返回 0。

        这一步把区间里的每个元素都看一遍再累加，看过几个元素就是几个元素的
        代价，区间一大就白扫，扫过的元素数记在 last_cost() 里方便观察。
        """
        self._check_range(left, right)
        total = 0
        self._last_cost = 0
        for i in range(left, right):
            total += self._data[i]
            self._last_cost += 1
        return total

    def last_cost(self):
        """返回上一次 range_sum 看过的元素个数。"""
        return self._last_cost

    def _check_index(self, index):
        if not isinstance(index, int) or isinstance(index, bool):
            raise ValueError("index must be an int")
        if index < 0 or index >= len(self._data):
            raise IndexError("index out of range: %r" % (index,))

    def _check_range(self, left, right):
        if not isinstance(left, int) or isinstance(left, bool):
            raise ValueError("left must be an int")
        if not isinstance(right, int) or isinstance(right, bool):
            raise ValueError("right must be an int")
        if left < 0 or right > len(self._data) or left > right:
            raise ValueError("bad range: [%r, %r)" % (left, right))
