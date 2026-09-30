"""朴素缓存实现：固定容量，访问时间戳全表重扫淘汰。

现状只有最近最少使用（LRU）这一种口径，且淘汰时每次都要线性扫描全部条目
挑出时间戳最旧的一个。结构上没有链表或堆，也没有过期时间、频次口径的概念。
"""


class Erro(Exception):
    """本库所有异常的基类。"""


class CacheError(Erro):
    """缓存非法操作，例如容量非法。"""


class LruCache:
    """朴素的固定容量最近最少使用缓存。

    内部用字典记录键到值，另外用一条独立递增的逻辑时间戳记录每个键的
    最近访问时刻。每次淘汰都把全部键扫一遍，取时间戳最小的那个。
    """

    def __init__(self, capacity):
        if not isinstance(capacity, int) or isinstance(capacity, bool):
            raise CacheError("capacity 必须是整数")
        if capacity <= 0:
            raise CacheError("capacity 必须为正")
        self._capacity = capacity
        self._data = {}
        self._seen = {}
        self._tick = 0
        self._evictions = 0

    def capacity(self):
        """容量上限。"""
        return self._capacity

    def __len__(self):
        return len(self._data)

    def __contains__(self, key):
        return key in self._data

    def keys(self):
        """按插入顺序返回当前键。"""
        return list(self._data.keys())

    def snapshot(self):
        """当前内容的浅拷贝。"""
        return dict(self._data)

    def _touch(self, key):
        self._tick += 1
        self._seen[key] = self._tick

    def get(self, key):
        """取一个键的值；命中算一次使用，未命中返回 None。"""
        if key in self._data:
            self._touch(key)
            return self._data[key]
        return None

    def put(self, key, value):
        """写入一个键值；已存在视为一次使用并更新值。"""
        if key in self._data:
            self._data[key] = value
            self._touch(key)
            return
        self._data[key] = value
        self._touch(key)
        if len(self._data) > self._capacity:
            self._evict()

    def _evict(self):
        """线性重扫全部条目，淘汰时间戳最小的那个键。"""
        oldest_key = None
        oldest_tick = None
        for key in self._data:
            tick = self._seen[key]
            if oldest_tick is None or tick < oldest_tick:
                oldest_tick = tick
                oldest_key = key
        del self._data[oldest_key]
        del self._seen[oldest_key]
        self._evictions += 1

    def evictions(self):
        """累计淘汰次数。"""
        return self._evictions
