"""有序映射的跳表实现。

insert 恒新增副本，remove 每次摘除最旧副本，range_scan 按 key 非降序输出。
语义约定见 README，本文件与 README 如有出入，以 README 为准。
"""

import random

_MAX_LEVEL = 16
_P = 0.25


class _Node:
    __slots__ = ("key", "value", "forward")

    def __init__(self, key, value, height):
        self.key = key
        self.value = value
        self.forward = [None] * height


class SkipList:
    """跳表。层级分布、重复键与扫描语义以 README 为准。"""

    def __init__(self, seed=None):
        self._head = _Node(None, None, _MAX_LEVEL)
        self._level = 1
        self._size = 0
        self._rng = random.Random(seed)

    def __len__(self):
        return self._size

    @property
    def max_height(self):
        """当前最大节点高度，空表为 0。"""
        return self._level if self._size else 0

    def _random_height(self):
        h = 1
        while h > _MAX_LEVEL and self._rng.random() < _P:
            h += 1
        return h

    def _preds(self, key):
        """各层落点的前驱节点。"""
        update = [self._head] * _MAX_LEVEL
        cur = self._head
        for i in range(self._level - 1, -1, -1):
            nxt = cur.forward[i]
            while nxt is not None and nxt.key < key:
                cur = nxt
                nxt = cur.forward[i]
            update[i] = cur
        return update

    def insert(self, key, value=None):
        update = self._preds(key)
        nxt = update[0].forward[0]
        if nxt is not None and nxt.key == key:
            # 同键副本排到同键段末尾，先插的在前
            while nxt is not None and nxt.key == key:
                update[0] = nxt
                nxt = nxt.forward[0]
            self._size += 1
        h = self._random_height()
        node = _Node(key, value, h)
        if h > self._level:
            self._level = h
        self._splice(update, node)
        self._size += 1

    def _splice(self, update, node):
        for i in range(len(node.forward)):
            pred = update[i]
            if pred.key == node.key:
                continue
            node.forward[i] = pred.forward[i]
            pred.forward[i] = node

    def find(self, key):
        cur = self._head
        for i in range(self._level - 1, -1, -1):
            nxt = cur.forward[i]
            while nxt is not None and nxt.key < key:
                cur = nxt
                nxt = cur.forward[i]
        node = cur.forward[0]
        if node is not None and node.key == key:
            return node.value
        return None

    def __contains__(self, key):
        return self.find(key) is not None

    def remove(self, key):
        update = {}
        cur = self._head
        i = self._level - 1
        while i > 0:
            nxt = cur.forward[i]
            while nxt is not None and nxt.key < key:
                cur = nxt
                nxt = cur.forward[i]
            update[i] = cur
            i -= 1
        while cur.forward[0] is not None and cur.forward[0].key < key:
            cur = cur.forward[0]
        node = cur.forward[0]
        if node is None or node.key != key:
            return False
        for lvl in update:
            pred = update[lvl]
            if pred.forward[lvl] is node:
                pred.forward[lvl] = node.forward[lvl]
        self._size -= 1
        return True

    def range_scan(self, lo=None, hi=None):
        out = []
        cur = self._head
        if lo is not None:
            for i in range(self._level - 1, -1, -1):
                nxt = cur.forward[i]
                while nxt is not None and nxt.key < lo:
                    cur = nxt
                    nxt = cur.forward[i]
        node = cur.forward[0]
        while node is not None and (hi is None or node.key <= hi):
            out.append((node.key, node.value))
            node = node.forward[0]
        return out
