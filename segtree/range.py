"""segtree.range

改造前基线：一个朴素区间数组的逐项实现。

所有区间操作都逐项扫一遍区间，改一个元素原先算过的区间结果都留不下来。
这里刻意不做任何加速与缓存，用途只是把现状行为锁住。
"""

__all__ = ["SegError", "IndexError", "RangeArray"]


class SegError(Exception):
    """本包所有异常的基类，基线里非法区间也走它。"""


class IndexError(SegError):
    """单点下标非法时抛出，fail fast，不把下标夹到合法范围。"""


def _check_slice(length, l, r):
    """校验半开区间 [l, r)，非法就 fail fast，不悄悄修正。"""
    if not isinstance(l, int) or not isinstance(r, int):
        raise ValueError("区间端点必须是整数")
    if l < 0 or r > length or l > r:
        raise ValueError("非法区间 [%r, %r)" % (l, r))


def _check_index(length, i):
    """校验单点下标 i，非法就 fail fast。"""
    if not isinstance(i, int):
        raise IndexError("下标必须是整数")
    if i < 0 or i >= length:
        raise IndexError("下标越界 %r" % (i,))


class RangeArray:
    """朴素区间数组。

    内部用一个 list 存数据。区间操作一律逐项扫过区间，没有任何树结构，
    也没有懒标记；每次调用都是独立的逐项计算，上次算过的结果留不下来。
    """

    def __init__(self, data=None):
        if data is None:
            data = []
        self._data = [int(v) for v in data]
        self._range_ops = 0

    # ---- 单点读写 ----

    def get(self, i):
        """返回第 i 个元素。"""
        _check_index(len(self._data), i)
        return self._data[i]

    def set(self, i, v):
        """把第 i 个元素设为 v，返回设置后的值。"""
        _check_index(len(self._data), i)
        self._data[i] = int(v)
        return self._data[i]

    # ---- 区间操作：一律逐项扫 ----

    def range_add(self, l, r, v):
        """对半开区间 [l, r) 逐项加 v。空区间无副作用。"""
        _check_slice(len(self._data), l, r)
        v = int(v)
        for i in range(l, r):
            self._data[i] += v
        self._range_ops += 1
        return None

    def range_sum(self, l, r):
        """逐项求 [l, r) 的和。空区间返回 0。"""
        _check_slice(len(self._data), l, r)
        total = 0
        for i in range(l, r):
            total += self._data[i]
        self._range_ops += 1
        return total

    def range_max(self, l, r):
        """逐项取 [l, r) 的最大值。空区间返回约定的 None。"""
        _check_slice(len(self._data), l, r)
        if l == r:
            self._range_ops += 1
            return None
        best = self._data[l]
        for i in range(l + 1, r):
            if self._data[i] > best:
                best = self._data[i]
        self._range_ops += 1
        return best

    # ---- 其它 ----

    def to_list(self):
        """返回当前数据的副本，供基线测试锁住现状。"""
        return list(self._data)

    def __len__(self):
        return len(self._data)

    def range_op_count(self):
        """到目前为止发生过的区间操作次数。"""
        return self._range_ops

    def __repr__(self):
        return "RangeArray(%r)" % (self._data,)
