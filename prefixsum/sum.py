"""prefixsum 的朴素逐项累加实现（改造前的现状）。

现在只有这一条路：一个区间和工具，点更新就是把某个下标的元素直接改掉，
区间求和就是从区间起点开始逐项累加。没有树状数组，没有按二进制的下标跳转，
没有差分，也没有二维结构。树状数组改造见任务描述。
"""


class ScanSum:
    """一串整数，区间求和只有从头逐项累加这一种做法。"""

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

    def update(self, index, delta):
        """把下标 index 处的元素加上增量 delta，返回加完之后的新值。"""
        self._check_index(index)
        if not isinstance(delta, int) or isinstance(delta, bool):
            raise ValueError("delta must be an int")
        self._data[index] += delta
        return self._data[index]

    def query(self, left, right):
        """返回半开区间 [left, right) 的和，空区间返回 0。

        这一步从区间起点开始把区间里的每个元素都看一遍再累加，看过几个元素
        就是几个元素的代价，区间一大就白扫，扫过的元素数记在 last_cost() 里
        方便观察。
        """
        self._check_range(left, right)
        total = 0
        self._last_cost = 0
        for i in range(left, right):
            total += self._data[i]
            self._last_cost += 1
        return total

    def last_cost(self):
        """返回上一次 query 看过的元素个数。"""
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
