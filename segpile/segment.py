"""段的数据结构与归并规则。

段内按键有序、key 唯一；段与段之间的 key 可以重叠。段的新旧按
(seq, sid) 比：seq 大的新，seq 相同则 sid 大的新，越新越能压住旧值。
"""


class Segment:
    """一段只读日志。

    sid: 段 id，全局唯一。
    seq: 版本号，滚段时递增。
    created: 段的出生时刻，取自注入时钟。
    """

    __slots__ = ("sid", "seq", "created", "items", "_index")

    def __init__(self, sid, pairs, seq=0, created=0.0):
        items = sorted(pairs, key=lambda kv: kv[0])
        keys = [k for k, _ in items]
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate key in segment")
        self.sid = sid
        self.seq = seq
        self.created = created
        self.items = tuple(items)
        self._index = dict(items)

    @property
    def size(self):
        """段里 key 的个数，也是它参与归并时的 IO 规模。"""
        return len(self.items)

    @property
    def order(self):
        """排序用的新旧坐标。"""
        return (self.seq, self.sid)

    def lookup(self, key):
        """段内查询，缺失返回 None。"""
        return self._index.get(key)

    def keys(self):
        """按键有序的 key 列表。"""
        return [k for k, _ in self.items]

    def as_pairs(self):
        """按键有序的 (key, value) 列表，返回新列表。"""
        return list(self.items)

    def __len__(self):
        return len(self.items)

    def __contains__(self, key):
        return key in self._index

    def __repr__(self):
        return "Segment(sid=%r, seq=%r, size=%d)" % (self.sid, self.seq, self.size)


def merge_pairs(blobs):
    """把若干段键值对并成一份，返回按键有序的列表。

    blobs 按旧到新排，同一个 key 后来的盖住先来的。
    """
    values = {}
    for pairs in blobs:
        for key, value in pairs:
            values[key] = value
    return sorted(values.items(), key=lambda kv: kv[0])


def merge_units(segments):
    """一次归并的 IO 单位数：读完所有输入，再写回整个结果。"""
    keys = set()
    for seg in segments:
        keys.update(seg.keys())
    return sum(seg.size for seg in segments) + len(keys)
