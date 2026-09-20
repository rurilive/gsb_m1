"""按层组织的内存表。

写入落在最新一层，某层条目数超过它那层的容量时，与下一层合并压实，
新层的值覆盖旧层的同名值。读取从新到旧逐层查找，命中即返回。

每层配一个布隆过滤器：读取先问过滤器，说肯定没有的层整层跳过不扫。
压实会改变键集，受影响层的过滤器一律用合并后的键集重建，杜绝假阴。
"""

import base64
import json

from .bloom import BloomFilter

DEFAULT_LEVEL_CAPACITY = 2
DEFAULT_RATIO = 4
DEFAULT_ERROR_RATE = 0.01
_IMAGE_MAGIC = "blooms-memtable"
_IMAGE_VERSION = 1


def _jsonable(value):
    """把单个键/值包一层标注，bytes 用 base64，其余保持原样（在包装层里）。"""
    if isinstance(value, bytes):
        return {"__type__": "bytes", "data": base64.b64encode(value).decode("ascii")}
    return {"__type__": "json", "data": value}


def _from_jsonable(value):
    if value["__type__"] == "bytes":
        return base64.b64decode(value["data"])
    return value["data"]


class MemTable:
    """分层内存表，层号越小越新。

    level_capacity: 第 0 层的条目上限。
    ratio: 相邻两层容量的倍数，每深一层上限乘一次，必须大于等于 2，
        否则合并会一路往下压不停。
    error_rate: 每层布隆过滤器的目标误判率，取值 (0, 1)。
    """

    def __init__(
        self,
        level_capacity=DEFAULT_LEVEL_CAPACITY,
        ratio=DEFAULT_RATIO,
        error_rate=DEFAULT_ERROR_RATE,
    ):
        if level_capacity < 1:
            raise ValueError("level_capacity must be >= 1")
        if ratio < 2:
            raise ValueError("ratio must be >= 2")
        if not 0.0 < float(error_rate) < 1.0:
            raise ValueError("error_rate must be in (0, 1)")
        self._level_capacity = level_capacity
        self._ratio = ratio
        self._error_rate = float(error_rate)
        # 从新到旧，下标即层号
        self._levels = [{}]
        self._filters = [self._new_filter()]
        self._puts = 0
        self._gets = 0
        self._hits = 0
        self._misses = 0
        self._filter_probes = 0
        self._filter_skips = 0

    def put(self, key, value):
        """写入键值。已存在的键以本次写入为准。"""
        self._puts += 1
        level = self._levels[0]
        is_new_key = key not in level
        level[key] = value
        if is_new_key:
            # 条目数超出建时容量（误判率会超目标）就按当前键集扩容重建
            if self._filters[0].items >= self._filters[0].expected_items:
                self._filters[0].rebuild(level)
            else:
                self._filters[0].add(key)
        self._compact(0)

    def get(self, key):
        """从新到旧逐层查找，未命中返回 None。"""
        self._gets += 1
        for index, level in enumerate(self._levels):
            if not self._filters[index].might_contain(key):
                self._filter_skips += 1
                continue
            self._filter_probes += 1
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
        per_level = self.filter_stats()
        level_rates = [item["estimated_false_positive_rate"] for item in per_level]
        combined = 1.0
        for rate in level_rates:
            combined *= 1.0 - rate
        return {
            "puts": self._puts,
            "gets": self._gets,
            "hits": self._hits,
            "misses": self._misses,
            "levels": len(self._levels),
            "error_rate": self._error_rate,
            "filter_probes": self._filter_probes,
            "filter_skips": self._filter_skips,
            "estimated_false_positive_rate": 1.0 - combined,
        }

    def filter_stats(self):
        """每层过滤器的参数与按条目数估算的误判率，按下标对应层号。"""
        return [
            {
                "items": filter_.items,
                "expected_items": filter_.expected_items,
                "saturated": filter_.saturated,
                "estimated_false_positive_rate": filter_.estimated_false_positive_rate,
            }
            for filter_ in self._filters
        ]

    def save(self, path):
        """落盘：层数据、每层过滤器（参数+位数组）、统计与构造参数一起写。"""
        image = {
            "magic": _IMAGE_MAGIC,
            "version": _IMAGE_VERSION,
            "params": {
                "level_capacity": self._level_capacity,
                "ratio": self._ratio,
                "error_rate": self._error_rate,
            },
            "levels": [
                [[_jsonable(key), _jsonable(value)] for key, value in level.items()]
                for level in self._levels
            ],
            "filters": [filter_.to_dict() for filter_ in self._filters],
            "counters": {
                "puts": self._puts,
                "gets": self._gets,
                "hits": self._hits,
                "misses": self._misses,
                "filter_probes": self._filter_probes,
                "filter_skips": self._filter_skips,
            },
        }
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(image, handle, ensure_ascii=False)

    @classmethod
    def load(cls, path):
        """save 的逆操作，镜像损坏或参数对不上直接报错。"""
        with open(path, "r", encoding="utf-8") as handle:
            image = json.load(handle)
        if not isinstance(image, dict) or image.get("magic") != _IMAGE_MAGIC:
            raise ValueError("invalid memtable image")
        if image.get("version") != _IMAGE_VERSION:
            raise ValueError("unsupported memtable image version")
        params = image["params"]
        table = cls(
            level_capacity=params["level_capacity"],
            ratio=params["ratio"],
            error_rate=params["error_rate"],
        )
        level_images = image["levels"]
        filter_images = image["filters"]
        if len(level_images) != len(filter_images):
            raise ValueError("memtable image levels and filters mismatch")
        table._levels = []
        table._filters = []
        for pairs, filter_image in zip(level_images, filter_images):
            level = {}
            for pair in pairs:
                key, value = _from_jsonable(pair[0]), _from_jsonable(pair[1])
                level[key] = value
            filter_ = BloomFilter.from_dict(filter_image)
            if abs(filter_.error_rate - table._error_rate) > 1e-15:
                raise ValueError("memtable image error_rate mismatch")
            if filter_.items != len(level):
                raise ValueError("filter image does not match level contents")
            table._levels.append(level)
            table._filters.append(filter_)
        counters = image["counters"]
        table._puts = counters["puts"]
        table._gets = counters["gets"]
        table._hits = counters["hits"]
        table._misses = counters["misses"]
        table._filter_probes = counters["filter_probes"]
        table._filter_skips = counters["filter_skips"]
        return table

    def _capacity_of(self, index):
        return self._level_capacity * (self._ratio ** index)

    def _new_filter(self, expected_items=None):
        return BloomFilter(expected_items or self._level_capacity, self._error_rate)

    def _compact(self, index):
        """从 index 层起向下合并，直到该层回到容量之内。"""
        while index < len(self._levels):
            if len(self._levels[index]) <= self._capacity_of(index):
                return
            if index + 1 == len(self._levels):
                self._levels.append({})
                self._filters.append(self._new_filter(self._capacity_of(index + 1)))
            # 新层覆盖旧层：先铺旧的，再用新层盖上去
            merged = dict(self._levels[index + 1])
            merged.update(self._levels[index])
            self._levels[index] = {}
            self._levels[index + 1] = merged
            # 键集变了：两层过滤器都不能留旧位数组，全部按合并后状态重建，
            # 否则刚并进来的键会被判成不存在（假阴）。
            self._filters[index] = self._new_filter(self._capacity_of(index))
            self._filters[index + 1].rebuild(
                merged, max(self._capacity_of(index + 1), len(merged))
            )
            index += 1
