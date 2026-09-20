"""按层组织的内存表。

写入落在最新一层，层条目数超过它那层的容量时，与下一层合并压实，
新层的值覆盖旧层同名值。读取从新到旧逐层查找，命中即返回。

每层各配一个布隆过滤器：查键先问过滤器，它说这层肯定没有就整层跳过，
说可能有才真扫该层。压实改变键集，受影响的两层过滤器当场按新键集
重建，杜绝假阴。
"""

import pickle

from .bloom import BloomFilter

DEFAULT_LEVEL_CAPACITY = 2
DEFAULT_RATIO = 4
DEFAULT_ERROR_RATE = 0.01
_TABLE_FORMAT_MAGIC = b"BLMT"
_TABLE_FORMAT_VERSION = 1


class MemTable:
    """分层内存表，层号越小越新。

    level_capacity: 第 0 层的条目上限。
    ratio: 相邻两层容量的倍数，每深一层上限乘一次，必须大于等于 2，
        否则合并会一路往下压不停。
    error_rate: 每层布隆过滤器的目标误判率，取值 (0, 1)。
    """

    def __init__(self, level_capacity=DEFAULT_LEVEL_CAPACITY, ratio=DEFAULT_RATIO,
                 error_rate=DEFAULT_ERROR_RATE):
        if level_capacity < 1:
            raise ValueError("level_capacity must be >= 1")
        if ratio < 2:
            raise ValueError("ratio must be >= 2")
        if not 0.0 < error_rate < 1.0:
            raise ValueError("error_rate must be in (0, 1)")
        self._level_capacity = level_capacity
        self._ratio = ratio
        self._error_rate = error_rate
        # 从新到旧，下标即层号
        self._levels = [{}]
        self._filters = [self._make_filter(0, ())]
        self._puts = 0
        self._gets = 0
        self._hits = 0
        self._misses = 0
        self._bloom_skips = 0
        self._bloom_scans = 0

    def put(self, key, value):
        """写入键值。已存在的键以本次写入为准。"""
        self._puts += 1
        self._levels[0][key] = value
        compacted = self._compact(0)
        if compacted:
            # 压实已按各层新键集重建过滤器，L0 被清空，直接对账即可
            if len(self._filters[0]) != len(self._levels[0]):
                self._filters[0].rebuild(self._levels[0], self._capacity_of(0))
        else:
            # add 内部按键去重，L0 未超容时过滤器容量也不会涨
            self._filters[0].add(key)

    def get(self, key):
        """从新到旧逐层查找：过滤器说没有的层整层跳过，未命中返回 None。"""
        self._gets += 1
        for index, level in enumerate(self._levels):
            if not self._filters[index].might_contain(key):
                self._bloom_skips += 1
                continue
            self._bloom_scans += 1
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
        rates = [flt.estimated_false_positive_rate() for flt in self._filters]
        return {
            "puts": self._puts,
            "gets": self._gets,
            "hits": self._hits,
            "misses": self._misses,
            "levels": len(self._levels),
            "bloom_skips": self._bloom_skips,
            "bloom_scans": self._bloom_scans,
            # 穿透 = 过滤器说可能有而真扫了的层数
            "bloom_penetrations": self._bloom_scans,
            # 整表误判率取各层按自身条目数估算值的最大者
            "bloom_estimated_error_rate": max(rates),
            "bloom_level_error_rates": rates,
        }

    def dump(self, path):
        """整表落盘：配置、各层键值、过滤器状态与计数一并保存。"""
        payload = {
            "level_capacity": self._level_capacity,
            "ratio": self._ratio,
            "error_rate": self._error_rate,
            "levels": self._levels,
            "filters": self._filters,
            "counters": {
                "puts": self._puts,
                "gets": self._gets,
                "hits": self._hits,
                "misses": self._misses,
                "bloom_skips": self._bloom_skips,
                "bloom_scans": self._bloom_scans,
            },
        }
        with open(path, "wb") as handle:
            handle.write(_TABLE_FORMAT_MAGIC)
            handle.write(bytes([_TABLE_FORMAT_VERSION]))
            pickle.dump(payload, handle)

    @classmethod
    def load(cls, path):
        """整表读回，过滤器参数与键集逐项对账，行为与统计同落盘前。"""
        with open(path, "rb") as handle:
            magic = handle.read(len(_TABLE_FORMAT_MAGIC))
            if magic != _TABLE_FORMAT_MAGIC:
                raise ValueError("not a MemTable file")
            version = handle.read(1)
            if version != bytes([_TABLE_FORMAT_VERSION]):
                raise ValueError("unsupported MemTable format version")
            payload = pickle.load(handle)
        table = cls(payload["level_capacity"], payload["ratio"], payload["error_rate"])
        levels = payload["levels"]
        filters = payload["filters"]
        if len(levels) != len(filters):
            raise ValueError("levels and filters count mismatch")
        for level, flt in zip(levels, filters):
            if set(level) != set(flt._items):
                raise ValueError("filter keys do not match level keys")
            if flt._error_rate != table._error_rate:
                raise ValueError("filter error_rate mismatch")
        table._levels = levels
        table._filters = filters
        counters = payload["counters"]
        table._puts = counters["puts"]
        table._gets = counters["gets"]
        table._hits = counters["hits"]
        table._misses = counters["misses"]
        table._bloom_skips = counters["bloom_skips"]
        table._bloom_scans = counters["bloom_scans"]
        return table

    def _make_filter(self, index, keys):
        """按该层容量建过滤器，容量至少容得下当前键集。"""
        capacity = self._capacity_of(index)
        expected = max(capacity, len(keys))
        flt = BloomFilter(expected, self._error_rate)
        flt.rebuild(keys, expected)
        return flt

    def _capacity_of(self, index):
        return self._level_capacity * (self._ratio ** index)

    def _compact(self, index):
        """从 index 层起向下合并，直到该层回到容量之内。返回是否发生过合并。"""
        moved = False
        while index < len(self._levels):
            if len(self._levels[index]) <= self._capacity_of(index):
                return moved
            if index + 1 == len(self._levels):
                self._levels.append({})
                self._filters.append(self._make_filter(index + 1, ()))
            # 新层覆盖旧层：先铺旧的，再用新层盖上去
            merged = dict(self._levels[index + 1])
            merged.update(self._levels[index])
            self._levels[index] = {}
            self._levels[index + 1] = merged
            # 键集变了：被清空的层与接收合并结果的层都必须重建，
            # 留着旧位数组会把新并进来的键判成不存在（假阴，死线）。
            self._filters[index] = self._make_filter(index, ())
            self._filters[index + 1] = self._make_filter(index + 1, merged)
            moved = True
            index += 1
        return moved
