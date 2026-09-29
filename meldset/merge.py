"""改造前的朴素实现：HeapMerge 以整体搬迁方式合并集合。

每个集合是一个 ``dict``，键为整数元素，值为该元素到某属性的映射
（属性值由调用方给定，本模块只负责搬运与查询，不解释属性含义）。

朴素口径：``union_sets(a, b)`` 会把参与合并的全部元素逐个搬迁到一个
新集合里，哪怕其中一侧很小，也要连同另一侧的大集合一起重写。元素越多、
合并越频繁，这种整体搬迁的代价就越明显。
"""

__all__ = ["HeapMerge", "MeldError", "UnknownSetError", "UnknownElementError"]


class MeldError(Exception):
    """本模块所有异常的基类。"""


class UnknownSetError(MeldError):
    """引用了不存在的集合。"""


class UnknownElementError(MeldError):
    """引用了集合中不存在的元素。"""


class HeapMerge:
    """维护若干整数集合，支持合并、查询属性与修改属性。

    集合以不透明句柄标识；句柄到当前存储的映射保存在实例上，
    因此模块级不持有任何可变状态，同一实例重复跑固定序列结果一致。
    """

    def __init__(self):
        # 句柄 -> dict，dict 的键是元素，值是属性映射
        self._sets = {}
        # 单调递增的句柄分配器
        self._next_handle = 0

    # ------------------------------------------------------------------
    # 集合的建立与删除
    # ------------------------------------------------------------------
    def make_set(self, elements=None):
        """新建一个集合，elements 为可迭代的整数元素；返回集合句柄。"""
        data = {}
        if elements is not None:
            for x in elements:
                data[x] = {}
        handle = self._next_handle
        self._next_handle += 1
        self._sets[handle] = data
        return handle

    def remove_set(self, a):
        """整体删除集合 a；此句柄之后不可再用。"""
        self._check_set(a)
        del self._sets[a]

    # ------------------------------------------------------------------
    # 合并（当前为整体搬迁）
    # ------------------------------------------------------------------
    def union_sets(self, a, b):
        """把集合 a 与 b 合并为一个集合，返回合并后的句柄。

        朴素实现：新建一个空集合，先把 a 的全部元素逐个搬迁进去，
        再把 b 的全部元素逐个搬迁进去，随后两个旧句柄作废。
        """
        self._check_set(a)
        self._check_set(b)
        merged = {}
        for x, attr in self._sets[a].items():
            merged[x] = dict(attr)
        for x, attr in self._sets[b].items():
            merged[x] = dict(attr)
        del self._sets[a]
        del self._sets[b]
        handle = self._next_handle
        self._next_handle += 1
        self._sets[handle] = merged
        return handle

    # ------------------------------------------------------------------
    # 查询与修改
    # ------------------------------------------------------------------
    def size_of(self, a):
        """返回集合 a 的元素个数。"""
        self._check_set(a)
        return len(self._sets[a])

    def query(self, a, x):
        """返回元素 x 在集合 a 中的属性映射（副本）。"""
        self._check_set(a)
        data = self._sets[a]
        if x not in data:
            raise UnknownElementError("元素不在该集合中: %r" % (x,))
        return dict(data[x])

    def set_attr(self, a, x, key, value):
        """把集合 a 中元素 x 的属性 key 设为 value。"""
        self._check_set(a)
        data = self._sets[a]
        if x not in data:
            raise UnknownElementError("元素不在该集合中: %r" % (x,))
        data[x][key] = value

    # ------------------------------------------------------------------
    # 内部校验
    # ------------------------------------------------------------------
    def _check_set(self, a):
        if a not in self._sets:
            raise UnknownSetError("未知集合句柄: %r" % (a,))
