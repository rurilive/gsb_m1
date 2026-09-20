"""按层组织的内存表。

写入落在最新一层，某层条目数超过它那层的容量时，与下一层合并压实，
新层的值覆盖旧层的同名值。读取从新到旧逐层查找，命中即返回。
"""

DEFAULT_LEVEL_CAPACITY = 2
DEFAULT_RATIO = 4


class MemTable:
    """分层内存表，层号越小越新。

    level_capacity: 第 0 层的条目上限。
    ratio: 相邻两层容量的倍数，每深一层上限乘一次，必须大于等于 2，
        否则合并会一路往下压不停。
    """

    def __init__(self, level_capacity=DEFAULT_LEVEL_CAPACITY, ratio=DEFAULT_RATIO):
        if level_capacity < 1:
            raise ValueError("level_capacity must be >= 1")
        if ratio < 2:
            raise ValueError("ratio must be >= 2")
        self._level_capacity = level_capacity
        self._ratio = ratio
        # 从新到旧，下标即层号
        self._levels = [{}]
        self._puts = 0
        self._gets = 0
        self._hits = 0
        self._misses = 0

    def put(self, key, value):
        """写入键值。已存在的键以本次写入为准。"""
        self._puts += 1
        self._levels[0][key] = value
        self._compact(0)

    def get(self, key):
        """从新到旧逐层查找，未命中返回 None。"""
        self._gets += 1
        for level in self._levels:
            if key in level:
                self._hits += 1
                return level[key]
        self._misses += 1
        return None

    def levels(self):
        """各层快照，列表下标即层号，0 最新。返回独立 dict，调用方随便改。"""
        return [dict(level) for level in self._levels]

    def __len__(self):
        return sum(len(level) for level in self._levels)

    def stats(self):
        """计数快照，返回独立 dict。"""
        return {
            "puts": self._puts,
            "gets": self._gets,
            "hits": self._hits,
            "misses": self._misses,
            "levels": len(self._levels),
        }

    def _capacity_of(self, index):
        return self._level_capacity * (self._ratio ** index)

    def _compact(self, index):
        """从 index 层起向下合并，直到该层回到容量之内。"""
        while index < len(self._levels):
            if len(self._levels[index]) <= self._capacity_of(index):
                return
            if index + 1 == len(self._levels):
                self._levels.append({})
            # 新层覆盖旧层：先铺旧的，再用新层盖上去
            merged = dict(self._levels[index + 1])
            merged.update(self._levels[index])
            self._levels[index] = {}
            self._levels[index + 1] = merged
            index += 1
