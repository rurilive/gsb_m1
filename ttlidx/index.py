"""一张内存字典索引（改造前的朴素基线）。

现有能力：按字符串主键存一份字段字典，写入或覆盖一条，按键取回字段的一份拷贝，
按键删除并回报是否删到，按写入顺序列出全部主键，问条数与命中未命中计数。
所有条目都不会过期，写进去就一直留着。
带 TTL 的惰性过期与主动过期、二级倒排索引、原子更新、时间窗扫描与并发清理尚未提供。
"""


class DictIndex:
    """永不过期的字典索引。

    entries 以字符串主键为键，值是该主键对应的一份字段字典。
    写入同名主键即覆盖，主键在首次写入时的位置保持不变。
    取回的字段是一份拷贝，改动它不会影响索引里存的内容。
    """

    def __init__(self):
        self._entries = {}
        self._hits = 0
        self._misses = 0

    def _check_key(self, key):
        if not isinstance(key, str) or not key:
            raise ValueError("key must be a non-empty string")
        return key

    def _check_fields(self, fields):
        if not isinstance(fields, dict):
            raise ValueError("fields must be a dict")
        for name in fields:
            if not isinstance(name, str) or not name:
                raise ValueError("field name must be a non-empty string")
        return fields

    def set(self, key, fields):
        """写入或覆盖一条，同名主键覆盖，位置不变，字段按值拷贝存下。"""
        self._check_key(key)
        self._check_fields(fields)
        self._entries[key] = dict(fields)

    def get(self, key):
        """按键取回字段的一份拷贝，键不存在返回 None，并记一次命中或未命中。"""
        self._check_key(key)
        entry = self._entries.get(key)
        if entry is None:
            self._misses += 1
            return None
        self._hits += 1
        return dict(entry)

    def delete(self, key):
        """按键删除，删到返回 True，键本来就不在返回 False。"""
        self._check_key(key)
        if key in self._entries:
            del self._entries[key]
            return True
        return False

    def keys(self):
        """按写入顺序给出全部主键的元组。"""
        return tuple(self._entries)

    def contains(self, key):
        """键是否在索引里。"""
        self._check_key(key)
        return key in self._entries

    def stats(self):
        """计数快照，返回独立的字典。"""
        return {
            "live": len(self._entries),
            "hits": self._hits,
            "misses": self._misses,
        }

    def __len__(self):
        return len(self._entries)

    def __repr__(self):
        return "DictIndex(live=%d)" % len(self._entries)
