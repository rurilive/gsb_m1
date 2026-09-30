"""sqrtds: 平铺列表上的朴素序列操作（改造前基线）。

内部只有一份平铺的 list，元素按构造给出的顺序保存，允许负数。所有区间
操作都把区间逐个重扫一遍：

- sum_range(left, right)：对区间内每个位置逐个累加
- add_range(left, right, delta)：对区间内每个位置逐个累加 delta
- max_range(left, right)：逐个比较出区间最大值
- count_range(left, right, value)：逐个比较，数出区间内等于 value 的个数
- get(index) / set(index, value)：直接读改数组里的单点值
- replay(values, operations)：依次回放一串操作，返回末态与逐步返回值

区间一律是左闭右开的半开区间 [left, right)，下标从 0 数起。每次操作都会
把区间里的元素逐个碰一遍，实例上累计着一个元素访问计数，规模一大，每次
操作的代价就随区间长度成正比，中间没有任何分块或层级结构可供复用。
"""


class SqrtdsError(Exception):
    """sqrtds 里所有可预期错误的基类。"""


class IndexOutOfRangeError(SqrtdsError):
    """下标越界或区间非法。"""


class EmptyRangeError(SqrtdsError):
    """对空区间取最大值。"""


class Sequence:
    """平铺列表上的朴素序列操作。"""

    def __init__(self, values=()):
        """用 values 建实例，内部存一份副本。"""
        self._data = list(values)
        self._element_touches = 0

    # -- 只读视图 ---------------------------------------------------------

    @property
    def data(self):
        """返回内部序列的副本。"""
        return list(self._data)

    def size(self):
        """序列长度。"""
        return len(self._data)

    @property
    def element_touches(self):
        """累计的元素访问次数。"""
        return self._element_touches

    def reset_touches(self):
        """把元素访问计数清零。"""
        self._element_touches = 0
        return self

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

    def sum_range(self, left, right):
        """半开区间 [left, right) 求和：对每个位置逐个累加，空区间返回 0。"""
        left, right = self._check_range(left, right)
        total = 0
        for i in range(left, right):
            self._element_touches += 1
            total += self._data[i]
        return total

    def add_range(self, left, right, delta):
        """半开区间 [left, right) 整体加 delta：对每个位置逐个累加。"""
        left, right = self._check_range(left, right)
        for i in range(left, right):
            self._element_touches += 1
            self._data[i] += delta
        return self

    def max_range(self, left, right):
        """半开区间 [left, right) 的最大值：逐个比较，空区间抛错。"""
        left, right = self._check_range(left, right)
        if left == right:
            raise EmptyRangeError("空区间没有最大值: [%r, %r)" % (left, right))
        self._element_touches += 1
        best = self._data[left]
        for i in range(left + 1, right):
            self._element_touches += 1
            if self._data[i] > best:
                best = self._data[i]
        return best

    def count_range(self, left, right, value):
        """半开区间 [left, right) 内等于 value 的个数：逐个比较。"""
        left, right = self._check_range(left, right)
        hits = 0
        for i in range(left, right):
            self._element_touches += 1
            if self._data[i] == value:
                hits += 1
        return hits

    # -- 朴素单点操作 -----------------------------------------------------

    def get(self, index):
        """直接读数组里的单点值。"""
        index = self._check_index(index)
        self._element_touches += 1
        return self._data[index]

    def set(self, index, value):
        """直接写数组里的单点值。"""
        index = self._check_index(index)
        self._element_touches += 1
        self._data[index] = value
        return self

    # -- 操作回放 ---------------------------------------------------------

    @staticmethod
    def replay(values, operations):
        """按 operations 依次回放，返回 (末态, 每步返回值) 二元组。

        每个操作是一个元组，首项是操作名，后面是参数：

        - ("sum", left, right)            -> 区间和
        - ("add", left, right, delta)     -> None
        - ("max", left, right)            -> 区间最大值
        - ("count", left, right, value)   -> 区间内等于 value 的个数
        - ("get", index)                  -> 单点值
        - ("set", index, value)           -> None

        回放在 values 的一份副本上原地进行，返回的末态是那份副本。
        """
        if isinstance(values, Sequence):
            work = Sequence(values.data)
        else:
            work = Sequence(values)
        results = []
        for op in operations:
            name = op[0]
            args = op[1:]
            if name == "sum":
                results.append(work.sum_range(*args))
            elif name == "add":
                work.add_range(*args)
                results.append(None)
            elif name == "max":
                results.append(work.max_range(*args))
            elif name == "count":
                results.append(work.count_range(*args))
            elif name == "get":
                results.append(work.get(*args))
            elif name == "set":
                work.set(*args)
                results.append(None)
            else:
                raise SqrtdsError("未知操作: %r" % (name,))
        return work.data, results
