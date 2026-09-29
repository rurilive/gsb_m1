"""beatsx.seg —— 朴素区间取最值结构（改造前基线）。

NaiveSeg 内部只保留一个整数数组，所有区间操作都逐项处理：
- 求和、取最大、取最小都是把区间内的元素逐个看一遍；
- 区间取较小值 / 区间取较大值都是把区间内的元素逐个改写；
- 因此任何一次操作都与区间长度成正比，改一个点也不会留下可复用的中间结果。

本文件是「改造前基线」，只描述并锁定现状行为，不含任何线段树或剪枝逻辑。
"""


class BeatsError(Exception):
    """beatsx 的异常基类，非法区间等错误统一从这里派生。"""


class NaiveSeg:
    """逐项处理的朴素区间结构。

    内部数组下标从零开始；所有区间均按半开区间 [l, r) 理解，
    要求 0 <= l <= r <= n。区间为空时求和返回 0，取最大 / 取最小返回 None，
    区间取较小值 / 取较大值则不产生任何改动。
    """

    def __init__(self, data):
        """用一批整数构造，拷贝输入数组，不改动调用方传入的对象。"""
        self._data = [self._check_int(v) for v in data]

    # ---- 基本访问 ------------------------------------------------------

    @property
    def n(self):
        """元素个数。"""
        return len(self._data)

    def to_list(self):
        """返回内部数组的副本，用于外部查看当前状态。"""
        return list(self._data)

    def get(self, i):
        """取下标 i 处的值，越界抛 BeatsError。"""
        if not isinstance(i, int) or isinstance(i, bool):
            raise BeatsError("下标必须是整数，得到 %r" % (i,))
        if i < 0 or i >= len(self._data):
            raise BeatsError("下标越界：%d，合法范围 [0, %d)" % (i, len(self._data)))
        return self._data[i]

    # ---- 区间查询 ------------------------------------------------------

    def range_sum(self, l, r):
        """逐项求和半开区间 [l, r)，空区间返回 0。"""
        l, r = self._check_range(l, r)
        total = 0
        for i in range(l, r):
            total += self._data[i]
        return total

    def range_max(self, l, r):
        """逐项取最大，空区间返回 None。"""
        l, r = self._check_range(l, r)
        if l >= r:
            return None
        best = self._data[l]
        for i in range(l + 1, r):
            if self._data[i] > best:
                best = self._data[i]
        return best

    def range_min(self, l, r):
        """逐项取最小，空区间返回 None。"""
        l, r = self._check_range(l, r)
        if l >= r:
            return None
        best = self._data[l]
        for i in range(l + 1, r):
            if self._data[i] < best:
                best = self._data[i]
        return best

    # ---- 区间取最值（逐项处理） ----------------------------------------

    def chmin(self, l, r, x):
        """把区间内每个元素改写为它与 x 的较小值，逐项处理。"""
        l, r = self._check_range(l, r)
        x = self._check_int(x)
        for i in range(l, r):
            if self._data[i] > x:
                self._data[i] = x
        return self

    def chmax(self, l, r, x):
        """把区间内每个元素改写为它与 x 的较大值，逐项处理。"""
        l, r = self._check_range(l, r)
        x = self._check_int(x)
        for i in range(l, r):
            if self._data[i] < x:
                self._data[i] = x
        return self

    # ---- 校验 ----------------------------------------------------------

    @staticmethod
    def _check_int(v):
        if isinstance(v, bool) or not isinstance(v, int):
            raise BeatsError("元素必须是整数，得到 %r" % (v,))
        return v

    def _check_range(self, l, r):
        for name, v in (("l", l), ("r", r)):
            if isinstance(v, bool) or not isinstance(v, int):
                raise BeatsError("区间端点 %s 必须是整数，得到 %r" % (name, v))
        if l < 0 or r < 0 or l > r or r > len(self._data):
            raise BeatsError(
                "非法区间 [%d, %d)，合法范围 0 <= l <= r <= %d"
                % (l, r, len(self._data))
            )
        return l, r
