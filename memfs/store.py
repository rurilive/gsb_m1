"""扁平字典式内存存储，纯标准库。

现有能力（基线）：

- 构造无参，内部一个字典把键直接映射到字节串，键就是普通字符串，不带任何路径语义；
- write 整体覆盖写入并按写入字节数返回长度，键为空或数据不是字节串当场拒绝；
- read 取回字节串，键不存在抛 KeyError；
- append 在已有内容后追加，键不存在则当新建，返回追加后的总长度；
- remove 删除键，返回是否真的删掉了；size 报某个键的字节数，缺键抛 KeyError；
- keys 按字典序返回全部键；clear 清空；支持 in 与 len。

当前没有任何目录概念，键之间彼此独立，没有路径、没有链接、没有配额。
"""


class MemStore:
    """键到字节串的扁平存储。

    键为非空字符串，值为字节串；所有方法对非法入参 fail fast。
    """

    def __init__(self):
        self._data = {}

    @staticmethod
    def _check_key(key):
        if not isinstance(key, str) or key == "":
            raise ValueError("key must be a non-empty str")

    @staticmethod
    def _check_data(data):
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("data must be bytes")

    def write(self, key, data):
        """整体覆盖写入，返回写入后的字节数。"""
        self._check_key(key)
        self._check_data(data)
        payload = bytes(data)
        self._data[key] = payload
        return len(payload)

    def read(self, key):
        """取回键对应的字节串，键不存在抛 KeyError。"""
        self._check_key(key)
        try:
            return self._data[key]
        except KeyError:
            raise KeyError(key) from None

    def append(self, key, data):
        """在已有内容后追加，键不存在则新建，返回追加后的总长度。"""
        self._check_key(key)
        self._check_data(data)
        current = self._data.get(key, b"")
        merged = current + bytes(data)
        self._data[key] = merged
        return len(merged)

    def remove(self, key):
        """删除键，返回是否真的删掉了。"""
        self._check_key(key)
        return self._data.pop(key, None) is not None

    def size(self, key):
        """键对应的字节数，键不存在抛 KeyError。"""
        self._check_key(key)
        try:
            return len(self._data[key])
        except KeyError:
            raise KeyError(key) from None

    def keys(self):
        """全部键，按字典序。"""
        return sorted(self._data)

    def clear(self):
        """清空全部键。"""
        self._data.clear()

    def __contains__(self, key):
        return isinstance(key, str) and key in self._data

    def __len__(self):
        return len(self._data)
