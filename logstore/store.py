"""一个朴素的内存 KV 存储。

当前实现就是一个字典：put 覆盖旧值，get 取当前值，delete 直接抹掉键。
没有落段、没有版本、没有合并，所有键都活在同一层里。
"""


class KVStore:
    """字典式的内存 KV。

    put(key, value) 写入或覆盖，返回是否覆盖了已有的键。
    get(key) 取当前值，键不存在返回 None。
    delete(key) 删除键，返回该键此前是否存在。
    keys() 返回当前存在的键，按升序。
    __contains__ / __len__ 支持 in 与 len。
    """

    def __init__(self):
        self._data = {}

    def put(self, key, value):
        overwritten = key in self._data
        self._data[key] = value
        return overwritten

    def get(self, key, default=None):
        return self._data.get(key, default)

    def delete(self, key):
        if key in self._data:
            del self._data[key]
            return True
        return False

    def keys(self):
        return sorted(self._data.keys())

    def items(self):
        return [(k, self._data[k]) for k in sorted(self._data.keys())]

    def __contains__(self, key):
        return key in self._data

    def __len__(self):
        return len(self._data)