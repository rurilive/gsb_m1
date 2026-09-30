"""有序多重集合：排序数组存放全部元素，插入删除靠列表搬移。

集合允许重复元素；查找用二分定位，但插入与删除都要把数组后半段整体搬移，
是线性代价，规模一大就是瓶颈。排名、前驱后继都靠排序后按序扫描或定位取值，
下标访问则直接按下标取出，没有多层索引可跳，也没有一层层下降的查找过程。
"""

import bisect


class SkipxError(Exception):
    """skipx 的错误基类，具体错误都从它派生。"""


class EmptyError(SkipxError):
    """在空集合上做需要元素的操作。"""


class NotFoundError(SkipxError):
    """要删除或定位的元素不在集合中。"""


class IndexError_(SkipxError):
    """下标越界（按位取值）。"""


class SortedBag:
    """排序数组实现的有序多重集合，作为跳表改造前的朴素基线。

    元素之间必须可比较（大小有序），允许重复。全部元素放在一个升序列表里，
    不做任何去重。查找走二分，插入删除走列表搬移。
    """

    def __init__(self, values=()):
        self._items = sorted(values)

    # -- 基本性质 --------------------------------------------------------
    def __len__(self):
        """集合中元素的个数（含重复）。"""
        return len(self._items)

    def is_empty(self):
        """是否为空。"""
        return not self._items

    def __contains__(self, value):
        """是否含有某元素，二分定位后比对。"""
        i = bisect.bisect_left(self._items, value)
        return i < len(self._items) and self._items[i] == value

    def items(self):
        """按升序返回全部元素的副本（含重复）。"""
        return list(self._items)

    # -- 增删 ------------------------------------------------------------
    def insert(self, value):
        """插入一个元素，返回 None；重复元素照常插入。"""
        i = bisect.bisect_left(self._items, value)
        self._items.insert(i, value)

    def discard(self, value):
        """删除一个等于 value 的元素；不存在返回 False，存在返回 True。"""
        i = bisect.bisect_left(self._items, value)
        if i < len(self._items) and self._items[i] == value:
            del self._items[i]
            return True
        return False

    def remove(self, value):
        """删除一个等于 value 的元素；不存在抛 NotFoundError。"""
        if not self.discard(value):
            raise NotFoundError(value)

    def pop_at(self, index):
        """删除并返回升序第 index 个元素（从 0 起）；越界抛 IndexError_。"""
        self._check_index(index)
        return self._items.pop(index)

    # -- 查询 ------------------------------------------------------------
    def find(self, value):
        """是否含有某元素，与 __contains__ 同口径。"""
        return self.__contains__(value)

    def at(self, index):
        """升序第 index 个元素（从 0 起）；越界抛 IndexError_。"""
        self._check_index(index)
        return self._items[index]

    def rank(self, value):
        """value 的排名，即严格小于 value 的元素个数（从 0 起）。"""
        return bisect.bisect_left(self._items, value)

    def predecessor(self, value):
        """严格小于 value 的最大元素；不存在抛 NotFoundError。"""
        i = bisect.bisect_left(self._items, value)
        if i == 0:
            raise NotFoundError(value)
        return self._items[i - 1]

    def successor(self, value):
        """严格大于 value 的最小元素；不存在抛 NotFoundError。"""
        i = bisect.bisect_right(self._items, value)
        if i >= len(self._items):
            raise NotFoundError(value)
        return self._items[i]

    def range_scan(self, lo, hi):
        """左闭右开区间 [lo, hi) 内的全部元素，含重复，按升序返回。

        lo 大于等于 hi 时返回空列表。
        """
        i = bisect.bisect_left(self._items, lo)
        out = []
        while i < len(self._items) and self._items[i] < hi:
            out.append(self._items[i])
            i += 1
        return out

    # -- 查找代价统计 ----------------------------------------------------
    def probe_count(self, value):
        """统计查找 value 时逐次比较的元素个数，返回整数。

        沿升序列表用一个指针从前向后逐个比较，命中即停；没命中则走到严格大于
        value 的位置或表尾才停。这个计数是对照跳表下降结点的朴素口径。
        """
        n = 0
        for x in self._items:
            n += 1
            if x >= value:
                break
        return n

    # -- 内部 ------------------------------------------------------------
    def _check_index(self, index):
        if not isinstance(index, int) or isinstance(index, bool):
            raise TypeError("下标必须是整数")
        if index < 0 or index >= len(self._items):
            raise IndexError_(index)
