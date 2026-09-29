"""有序映射：排序数组加旁路字典，bisect 定位。

键可比较，按键唯一且升序维护；值放在旁路字典里。查找与定位是 O(log n)，
但插入与删除都要把数组后半段整体搬移，是 O(n)。键规模化之后这个搬移成本是瓶颈，
而且没有排名、也没有可复现的随机层级。
"""

import bisect


class SortedMap:
    """排序数组实现的有序映射，作为跳表改造前的朴素基线。"""

    def __init__(self):
        self._keys = []
        self._values = {}

    def __setitem__(self, key, value):
        """插入或覆盖 key：新键返回 True，覆盖已有键返回 False。"""
        if key is None:
            raise TypeError("key 不能为 None")
        i = bisect.bisect_left(self._keys, key)
        if i < len(self._keys) and self._keys[i] == key:
            self._values[key] = value
            return False
        self._keys.insert(i, key)
        self._values[key] = value
        return True

    def __getitem__(self, key):
        """按键取值，不存在抛 KeyError。"""
        if key not in self._values:
            raise KeyError(key)
        return self._values[key]

    def __delitem__(self, key):
        """按键删除，不存在抛 KeyError。"""
        i = bisect.bisect_left(self._keys, key)
        if i >= len(self._keys) or self._keys[i] != key:
            raise KeyError(key)
        del self._keys[i]
        del self._values[key]

    def get(self, key, default=None):
        """按键取值，不存在返回 default。"""
        return self._values.get(key, default)

    def __contains__(self, key):
        return key in self._values

    def __len__(self):
        return len(self._keys)

    def keys(self):
        """按键升序返回全部键的副本。"""
        return list(self._keys)

    def items(self):
        """按键升序返回 (key, value) 列表。"""
        return [(k, self._values[k]) for k in self._keys]

    def range(self, lo, hi):
        """扫描左闭右开区间 [lo, hi)，返回按键升序的 (key, value) 列表。

        lo 大于等于 hi 返回空列表。
        """
        i = bisect.bisect_left(self._keys, lo)
        out = []
        while i < len(self._keys) and self._keys[i] < hi:
            k = self._keys[i]
            out.append((k, self._values[k]))
            i += 1
        return out

    def first(self):
        """最小的 (key, value)，空映射返回 None。"""
        if not self._keys:
            return None
        k = self._keys[0]
        return (k, self._values[k])
