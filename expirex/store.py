"""带上限的字典，纯标准库。

现有能力（基线）：

- 构造只要一个 capacity，容量是条目的最大条数；
- set 写入键值，已有键直接改值，新键在容量满时先删掉一个键；
- get 命中返回值，未命中返回 None；
- 删除挑的是当前字典里第一个键，没有淘汰顺序、没有访问序；
- 条目一旦写进去就永远留着，没有过期时间，也没有清理。

当前实现是最朴素的一版：满了就随意删掉一个键，别的一概不管。
"""


class LimitedDict:
    """带上限的字典，容量满了随意删掉一个键。

    capacity 是条目数上限；到达上限后写入新键会先删掉一个已有键，
    删哪个不做保证。
    """

    def __init__(self, capacity):
        capacity = int(capacity)
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self.capacity = capacity
        self._data = {}

    def get(self, key):
        """命中返回值，未命中返回 None。"""
        return self._data.get(key)

    def set(self, key, value):
        """写入键值。新键在容量满时先删掉一个键。"""
        if key not in self._data and len(self._data) >= self.capacity:
            victim = next(iter(self._data))
            del self._data[victim]
        self._data[key] = value

    def delete(self, key):
        """删除键，键不存在时什么都不做。"""
        self._data.pop(key, None)

    def __contains__(self, key):
        return key in self._data

    def __len__(self):
        return len(self._data)

    def keys(self):
        """当前条目键，按插入顺序。"""
        return list(self._data)
