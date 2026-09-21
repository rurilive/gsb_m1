"""AWORSet：带因果上下文的添加胜出观察移除集合（add-wins OR-Set）。

每次加入生成全局唯一的点 (replica_id, seq)；删除只作用于删除方
已经看到的点，并发加入对删除不可见，因此合并后存活——添加胜出。
版本向量 clock 记录每个副本已连续看到的序号，是被删点的因果屏障；
时钟覆盖不到的被删点暂存为墓碑，时钟追上后即可安全回收。
合并满足交换律、结合律、幂等。
"""

import json


class AWORSet:
    """添加胜出的可移除集合，元素需可排序；落盘时元素需为 JSON 标量。

    replica_id: 本副本标识，非空字符串。
    """

    def __init__(self, replica_id):
        if not isinstance(replica_id, str) or not replica_id:
            raise ValueError("replica_id must be a non-empty string")
        self.replica_id = replica_id
        self._counter = 0
        self._clock = {}          # replica_id -> 已连续看到的最大序号
        self._live = {}           # item -> set of (replica_id, seq)
        self._tombstones = set()  # 被删但时钟尚未覆盖的点

    def add(self, item):
        """加入元素；若元素曾被移除，本次加入生成新点使其复活。"""
        self._counter += 1
        self._clock[self.replica_id] = self._counter
        # 本次加入观察到该元素现存的点，一并作废
        for old in self._live.get(item, ()):
            self._retire(old)
        self._live[item] = {(self.replica_id, self._counter)}
        return self

    def discard(self, item):
        """移除元素，只作用于本副本已看到的点。"""
        for dot in self._live.pop(item, ()):
            self._retire(dot)
        return self

    def contains(self, item):
        """元素当前是否在集合里。"""
        return bool(self._live.get(item))

    def value(self):
        """当前元素，按升序排列的元组。"""
        return tuple(sorted(self._live))

    def tombstone_count(self):
        """当前留存的墓碑数量。"""
        return len(self._tombstones)

    def gc(self):
        """回收已被因果时钟覆盖的墓碑，返回回收数量。"""
        kept = {d for d in self._tombstones if d[1] > self._clock.get(d[0], 0)}
        collected = len(self._tombstones) - len(kept)
        self._tombstones = kept
        return collected

    def merge(self, other):
        """就地并入另一个副本，返回自身。"""
        if not isinstance(other, AWORSet):
            raise TypeError("can only merge with AWORSet")
        other_live = set().union(*other._live.values()) if other._live else set()
        self_live = set().union(*self._live.values()) if self._live else set()

        new_clock = dict(self._clock)
        for rid, seq in other._clock.items():
            if seq > new_clock.get(rid, 0):
                new_clock[rid] = seq

        new_live = {}
        for item in set(self._live) | set(other._live):
            dots = {d for d in self._live.get(item, ())
                    if not self._removed_by(d, other, other_live)}
            dots |= {d for d in other._live.get(item, ())
                     if not self._removed_by(d, self, self_live)}
            if dots:
                new_live[item] = dots

        self._clock = new_clock
        self._live = new_live
        self._tombstones |= other._tombstones
        self.gc()
        return self

    @staticmethod
    def _removed_by(dot, state, state_live):
        """state 是否已看到 dot 且没有让它存活。"""
        if dot in state_live:
            return False
        return dot in state._tombstones or dot[1] <= state._clock.get(dot[0], 0)

    def _retire(self, dot):
        """作废一个点：时钟已覆盖则无需留痕，否则记为墓碑。"""
        if dot[1] > self._clock.get(dot[0], 0):
            self._tombstones.add(dot)

    def to_dict(self):
        """编码为 JSON 兼容的纯字典，可传输可落盘。"""
        return {
            "type": "AWORSet",
            "replica_id": self.replica_id,
            "counter": self._counter,
            "clock": {rid: self._clock[rid] for rid in sorted(self._clock)},
            "live": [[item, sorted(map(list, dots))]
                     for item, dots in sorted(self._live.items(),
                                              key=lambda kv: repr(kv[0]))],
            "tombstones": sorted(map(list, self._tombstones)),
        }

    @classmethod
    def from_dict(cls, data):
        """从 to_dict 的字典还原，不丢因果信息。"""
        if not isinstance(data, dict) or data.get("type") != "AWORSet":
            raise ValueError("not an AWORSet payload")
        s = cls(data["replica_id"])
        s._counter = data["counter"]
        s._clock = {rid: int(seq) for rid, seq in data["clock"].items()}
        s._live = {item: {(rid, seq) for rid, seq in dots}
                   for item, dots in data["live"]}
        s._tombstones = {(rid, seq) for rid, seq in data["tombstones"]}
        return s

    def dumps(self):
        """编码为 JSON 字符串。"""
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)

    @classmethod
    def loads(cls, text):
        """从 dumps 的 JSON 字符串还原。"""
        return cls.from_dict(json.loads(text))

    def __repr__(self):
        return f"AWORSet({self.replica_id!r}, {list(self.value())!r})"
