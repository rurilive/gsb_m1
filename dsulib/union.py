"""连通集合的朴素实现（改造前基线）。

维护一张 元素 -> 所属集合 的映射，每个集合就是一个 Python set。
union 线性地重建集合，所有查询都要按当前映射逐次核算。
"""


class Recompute:
    """朴素连通集合。

    内部用两张表：元素到自身集合的 ``_parent_of``，以及元素到集合的
    ``_members``。任何写操作都可能重建集合对象，规模一大就慢。
    """

    def __init__(self):
        self._members = {}          # element -> set of elements
        self._parent_of = {}        # element -> the set it belongs to

    # ---- 写入 ----------------------------------------------------------

    def add(self, x):
        """加入一个此前不存在的元素，自成单元素集合。"""
        if x is None:
            raise ValueError("元素不能为空")
        if x in self._parent_of:
            raise ValueError("元素已存在: {!r}".format(x))
        s = {x}
        self._members[x] = s
        self._parent_of[x] = s

    def union(self, a, b):
        """把 a、b 所在的两个集合合并，返回合并后的集合大小。"""
        self._require(a)
        self._require(b)
        sa = self._parent_of[a]
        sb = self._parent_of[b]
        if sa is sb:
            # 已经同属一个集合，幂等，仍按当前集合大小返回。
            return len(sa)
        merged = set()
        for item in sa:
            merged.add(item)
        for item in sb:
            merged.add(item)
        # 线性重建：集合里每个元素都要重新指向新集合。
        for item in merged:
            self._parent_of[item] = merged
            self._members[item] = merged
        return len(merged)

    # ---- 查询 ----------------------------------------------------------

    def connected(self, a, b):
        """判断 a 与 b 是否落在同一个集合。"""
        self._require(a)
        self._require(b)
        return self._parent_of[a] is self._parent_of[b]

    def component_size(self, x):
        """x 所在集合的元素个数。"""
        self._require(x)
        return len(self._parent_of[x])

    def count_components(self):
        """遍历统计当前不同集合的个数。"""
        seen = []
        for s in self._members.values():
            if s not in seen:
                seen.append(s)
        return len(seen)

    def members(self, x):
        """返回 x 所在集合全部元素的拷贝。"""
        self._require(x)
        return set(self._parent_of[x])

    # ---- 内部 ----------------------------------------------------------

    def _require(self, x):
        if x is None:
            raise ValueError("元素不能为空")
        if x not in self._parent_of:
            raise ValueError("元素不存在: {!r}".format(x))
        return self._parent_of[x]
