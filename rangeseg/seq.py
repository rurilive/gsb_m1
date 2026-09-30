"""RangeSeq: 平铺列表上的朴素区间操作（改造前基线）。

内部只有一份平铺的 list，元素按构造给出的顺序保存，允许负数。所有区间
操作都把整段重扫一遍：

- sum(left, right)：逐个累加半开区间 [left, right) 内的元素
- add(left, right, delta)：逐个把区间内的元素加上 delta
- assign(left, right, value)：逐个把区间内的元素改写成 value
- min_val(left, right) / max_val(left, right)：逐个比较出区间最值
- get(index) / set(index, value)：按下标读改单点值
- replay(values, operations)：依次回放一串操作，返回末态与逐步返回值
- taken()：至今为止逐项扫描累计访问过的元素次数

区间一律是左闭右开的半开区间 [left, right)，下标从 0 数起。规模一大，
每次区间操作的代价就随区间长度线性上涨，中间没有任何层级结构可供复用，
也没有标记可以留待以后下推。每一次扫描都把访问过的元素个数累加进计数器。
"""


class RangeSegError(Exception):
    """rangeseg 里所有可预期错误的基类。"""


class IndexOutOfRangeError(RangeSegError):
    """下标越界或区间次序颠倒。"""


class EmptySequenceError(RangeSegError):
    """对空区间取最值。"""


class RangeSeq:
    """平铺列表上的朴素区间操作。"""

    def __init__(self, values=()):
        """用 values 建实例，内部存一份副本。"""
        self._data = list(values)
        self._taken = 0

    # -- 只读视图 ---------------------------------------------------------

    @property
    def data(self):
        """返回内部序列的副本。"""
        return list(self._data)

    def size(self):
        """序列长度。"""
        return len(self._data)

    def taken(self):
        """至今为止逐项扫描累计访问过的元素次数。"""
        return self._taken

    # -- 内部校验 ---------------------------------------------------------

    def _check_range(self, left, right):
        """检查半开区间 [left, right) 是否合法，非法就地快速失败。"""
        n = len(self._data)
        if not isinstance(left, int) or not isinstance(right, int):
            raise IndexOutOfRangeError("区间端点必须是整数: %r %r" % (left, right))
        if not (0 <= left <= right <= n):
            raise IndexOutOfRangeError(
                "区间越界或次序颠倒: [%r, %r)" % (left, right)
            )
        return left, right

    def _check_index(self, index):
        """检查单点下标是否合法，非法就地快速失败。"""
        n = len(self._data)
        if not isinstance(index, int):
            raise IndexOutOfRangeError("下标必须是整数: %r" % (index,))
        if not (0 <= index < n):
            raise IndexOutOfRangeError("下标越界: %r" % (index,))
        return index

    # -- 朴素区间操作 -----------------------------------------------------

    def sum(self, left, right):
        """半开区间 [left, right) 求和：逐个累加，空区间返回 0。"""
        left, right = self._check_range(left, right)
        total = 0
        for i in range(left, right):
            total += self._data[i]
            self._taken += 1
        return total

    def add(self, left, right, delta):
        """半开区间 [left, right) 整体加 delta：逐个改写。"""
        left, right = self._check_range(left, right)
        for i in range(left, right):
            self._data[i] += delta
            self._taken += 1
        return self

    def assign(self, left, right, value):
        """半开区间 [left, right) 整体改写成 value：逐个改写。"""
        left, right = self._check_range(left, right)
        for i in range(left, right):
            self._data[i] = value
            self._taken += 1
        return self

    def min_val(self, left, right):
        """半开区间 [left, right) 的最小值：逐个比较，空区间抛错。"""
        left, right = self._check_range(left, right)
        if left == right:
            raise EmptySequenceError("空区间没有最值: [%r, %r)" % (left, right))
        best = self._data[left]
        self._taken += 1
        for i in range(left + 1, right):
            if self._data[i] < best:
                best = self._data[i]
            self._taken += 1
        return best

    def max_val(self, left, right):
        """半开区间 [left, right) 的最大值：逐个比较，空区间抛错。"""
        left, right = self._check_range(left, right)
        if left == right:
            raise EmptySequenceError("空区间没有最值: [%r, %r)" % (left, right))
        best = self._data[left]
        self._taken += 1
        for i in range(left + 1, right):
            if self._data[i] > best:
                best = self._data[i]
            self._taken += 1
        return best

    # -- 朴素单点操作 -----------------------------------------------------

    def get(self, index):
        """按下标读单点值。"""
        index = self._check_index(index)
        self._taken += 1
        return self._data[index]

    def set(self, index, value):
        """按下标写单点值。"""
        index = self._check_index(index)
        self._data[index] = value
        self._taken += 1
        return self

    # -- 操作回放 ---------------------------------------------------------

    @staticmethod
    def replay(values, operations):
        """按 operations 依次回放，返回 (末态, 每步返回值) 二元组。

        每个操作是一个元组，首项是操作名，后面是参数：

        - ("sum", left, right)           -> 区间和
        - ("add", left, right, delta)    -> None
        - ("assign", left, right, value) -> None
        - ("min", left, right)           -> 区间最小值
        - ("max", left, right)           -> 区间最大值
        - ("get", index)                 -> 单点值
        - ("set", index, value)          -> None

        回放在 values 的一份副本上原地进行，返回的末态是那份副本。
        """
        if isinstance(values, RangeSeq):
            work = RangeSeq(values.data)
        else:
            work = RangeSeq(values)
        results = []
        for op in operations:
            name = op[0]
            args = op[1:]
            if name == "sum":
                results.append(work.sum(*args))
            elif name == "add":
                work.add(*args)
                results.append(None)
            elif name == "assign":
                work.assign(*args)
                results.append(None)
            elif name == "min":
                results.append(work.min_val(*args))
            elif name == "max":
                results.append(work.max_val(*args))
            elif name == "get":
                results.append(work.get(*args))
            elif name == "set":
                work.set(*args)
                results.append(None)
            else:
                raise RangeSegError("未知操作: %r" % (name,))
        return work.data, results
