"""rankerx 的朴素下一个更大元素实现（改造前的现状）。

现在只有这一条路：对每个位置，从它后面挨个往后看，找到第一个比它大的值就
停下，找不到就用约定值 -1 表示无后继。没有单调栈，没有一次遍历，没有区间，
也还没有更小、前面、直方图、天数、跨度与滑动窗口这些查询。单调栈系列改造
见任务描述。
"""


class RankxError(Exception):
    """rankerx 所有异常的基类。"""


class BruteNext:
    """一串整数，下一个更大元素只有逐个往后找这一种做法。"""

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

    def next_greater(self, index):
        """返回下标 index 处元素的下一个更大元素，没有则返回约定值 -1。

        做法就是从 index 的下一位开始挨个往后看，谁先比它大就返回谁，一直
        到最后都没有更大的就返回 -1。看过几个元素就是几个元素的代价，区间
        一长就白扫。
        """
        self._check_index(index)
        base = self._data[index]
        for j in range(index + 1, len(self._data)):
            if self._data[j] > base:
                return self._data[j]
        return -1

    def next_greater_all(self):
        """返回每个位置的下一个更大元素组成的列表，无后继的位置为约定值 -1。"""
        return [self.next_greater(i) for i in range(len(self._data))]

    def _check_index(self, index):
        if not isinstance(index, int) or isinstance(index, bool):
            raise ValueError("index must be an int")
        if index < 0 or index >= len(self._data):
            raise IndexError("index out of range: %r" % (index,))
