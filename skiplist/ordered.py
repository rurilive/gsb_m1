"""有序映射：排序列表加字典，bisect 定位。

键可比较，按升序维护；值放在旁路字典里。查找与定位是 O(log n)，
但插入要把列表后半段整体后移，是 O(n)。键规模化之后这个搬移成本是瓶颈。
"""

import bisect


class OrderedMap:
    """排序列表实现的有序映射。"""

    def __init__(self):
        self._keys = []
        self._values = {}

    def put(self, key, value):
        """插入或覆盖 key。

        键已存在则覆盖其值并返回 False；是新键则插入并返回 True。
        """
        i = bisect.bisect_left(self._keys, key)
        if i < len(self._keys) and self._keys[i] == key:
            self._values[key] = value
            return False
        self._keys.insert(i, key)
        self._values[key] = value
        return True

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

    def range_scan(self, lo, hi):
        """扫描闭区间 [lo, hi]，返回按键升序的 (key, value) 列表。

        两端等号都算；lo 大于 hi 返回空列表。
        """
        i = bisect.bisect_left(self._keys, lo)
        out = []
        while i < len(self._keys) and self._keys[i] <= hi:
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
