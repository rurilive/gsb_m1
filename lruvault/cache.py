"""采集服务在用的 LRU 缓存。上个月接入多线程网关时加了一把锁。"""

import threading

from .nodes import Node, OrderList
from .stats import Stats, hit_rate


class LRUCache:
    """容量满时按最久未用淘汰，get/put/delete 的计数走 stats()。

    约定：key 与 value 都不许是 None；put 覆盖已有键不算命中；
    淘汰回调 on_evict(key, value) 在发生容量淘汰时同步调用一次，
    手上拿到的是被淘汰键在淘汰前的值；delete 主动删除不触发回调。
    """

    def __init__(self, capacity, on_evict=None):
        if capacity < 1:
            raise ValueError("capacity 至少为 1")
        self._capacity = int(capacity)
        self._on_evict = on_evict
        self._lock = threading.Lock()
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
        """当前键数。"""
        return len(self._data)

    def keys(self):
        """从新到旧列出键。"""
        return [node.key for node in self._order.nodes()]

    def snapshot(self):
        """从新到旧列出 (key, value)，本身不动新旧次序。"""
        return [(node.key, node.value) for node in self._order.nodes()]

    def contains(self, key):
        return key in self._data

    def get(self, key, default=None):
        """命中就把键挪到最新并返回值，不命中给 default。"""
        node = self._data.get(key)
        if node is None:
            with self._lock:
                self._misses += 1
            return default
        with self._lock:
            self._hits += 1
        self._order.touch(node)
        return node.value

    def put(self, key, value):
        """写入或覆盖；顺带把超额的旧键淘汰掉。"""
        if key is None or value is None:
            raise ValueError("key 和 value 都不能是 None")
        node = self._data.get(key)
        if node is not None:
            with self._lock:
                node.value = value
                self._puts += 1
            self._order.touch(node)
            return
        fresh = Node(key, value)
        with self._lock:
            current = self._data.get(key)
            if current is not None:
                current.value = value
                self._puts += 1
                self._hits += 1
                self._order.touch(current)
                return
            self._data[key] = fresh
            self._order.push_front(fresh)
            self._puts += 1
            self._trim_locked()

    def delete(self, key):
        """删掉键，返回是否真删到了；不触发淘汰回调。"""
        node = self._data.pop(key, None)
        if node is None:
            return False
        self._order.unlink(node)
        node.clear()
        with self._lock:
            self._deletes += 1
        return True

    def stats(self):
        """当前计数快照。"""
        return Stats(self._hits, self._misses, self._evictions,
                     self._puts, self._deletes, len(self._data))

    def hit_rate(self):
        """命中率，口径见 stats.py。"""
        return hit_rate(self.stats())

    def _trim_locked(self):
        """在持锁状态下把超额的键从最旧的开始淘汰。"""
        while len(self._data) > self._capacity:
            victim = self._order.pop_back()
            if victim is None:
                break
            removed = self._data.pop(victim.key, None)
            if removed is None:
                continue
            self._evictions += 1
            evicted_key, evicted_value = victim.key, victim.value
            victim.clear()
            if self._on_evict is not None:
                self._on_evict(evicted_key, evicted_value)
