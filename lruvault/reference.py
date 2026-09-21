"""单线程参考实现与随机操作生成器，只给对拍用，线上路径别依赖这里。"""

import random

from .nodes import Node, OrderList
from .stats import Stats, hit_rate


class PlainLRU:
    """没加锁的老实现，语义与 LRUCache 逐条对齐：同一个键在同一个位置上，
    get/put/delete 的计数也按 stats.py 的同一套口径报。"""

    def __init__(self, capacity, on_evict=None):
        if capacity < 1:
            raise ValueError("capacity 至少为 1")
        self._capacity = int(capacity)
        self._on_evict = on_evict
        self._data = {}
        self._order = OrderList()
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._puts = 0
        self._deletes = 0

    @property
    def capacity(self):
        return self._capacity

    def __len__(self):
        return len(self._data)

    def __contains__(self, key):
        return key in self._data

    def size(self):
        return len(self._data)

    def keys(self):
        return [node.key for node in self._order.nodes()]

    def snapshot(self):
        return [(node.key, node.value) for node in self._order.nodes()]

    def contains(self, key):
        return key in self._data

    def get(self, key, default=None):
        node = self._data.get(key)
        if node is None:
            self._misses += 1
            return default
        self._hits += 1
        self._order.touch(node)
        return node.value

    def put(self, key, value):
        if key is None or value is None:
            raise ValueError("key 和 value 都不能是 None")
        node = self._data.get(key)
        if node is not None:
            node.value = value
            self._puts += 1
            self._order.touch(node)
            return
        node = Node(key, value)
        self._data[key] = node
        self._order.push_front(node)
        self._puts += 1
        while len(self._data) > self._capacity:
            victim = self._order.pop_back()
            if victim is None:
                break
            del self._data[victim.key]
            self._evictions += 1
            evicted_key, evicted_value = victim.key, victim.value
            victim.clear()
            if self._on_evict is not None:
                self._on_evict(evicted_key, evicted_value)

    def delete(self, key):
        node = self._data.pop(key, None)
        if node is None:
            return False
        self._order.unlink(node)
        node.clear()
        self._deletes += 1
        return True

    def stats(self):
        return Stats(self._hits, self._misses, self._evictions,
                     self._puts, self._deletes, len(self._data))

    def hit_rate(self):
        return hit_rate(self.stats())


def random_ops(seed, count, key_space, get_share=0.5, put_share=0.35):
    """造一段随机操作序列：("get", key, None) / ("put", key, value) /
    ("delete", key, None)。同样的 seed 出同样的序列。"""
    rng = random.Random(seed)
    ops = []
    for index in range(count):
        roll = rng.random()
        key = rng.randrange(key_space)
        if roll < get_share:
            ops.append(("get", key, None))
        elif roll < get_share + put_share:
            ops.append(("put", key, "v%d-%d" % (key, index)))
        else:
            ops.append(("delete", key, None))
    return ops


def apply_ops(target, ops, default=None):
    """把操作序列打给任意一个实现了同一套接口的缓存，返回每次 get 的结果。"""
    results = []
    for kind, key, value in ops:
        if kind == "get":
            results.append(target.get(key, default))
        elif kind == "put":
            target.put(key, value)
        elif kind == "delete":
            target.delete(key)
        else:
            raise ValueError("不认识的操作 %r" % (kind,))
    return results
