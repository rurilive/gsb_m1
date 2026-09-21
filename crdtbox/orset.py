"""ORSet：带因果上下文的添加胜出观测移除集（add-wins observed-remove set）。

每次加入打上一个全局唯一的点（replica_id, 序号），删除只移除自己
观测到的那些点，并把它们连同删除时刻的因果上下文（版本向量快照）
记为墓碑。合并时按对方的时钟与墓碑过滤点，并发加入天然胜出；
合并满足交换律、结合律、幂等。

所有已知副本的时钟都覆盖某次删除的上下文后，墓碑即可被 gc() 回收；
回收后靠版本向量挡住还在路上的旧状态，已删元素不会复活。
"""


def _vv_max(left, right):
    """两个版本向量逐槽取大。"""
    merged = dict(left)
    for replica, seq in right.items():
        if seq > merged.get(replica, 0):
            merged[replica] = seq
    return merged


def _vv_dominates(clock, context):
    """clock 是否覆盖 context（context 里每个槽位都不超过 clock）。"""
    return all(clock.get(replica, 0) >= seq for replica, seq in context.items())


class ORSet:
    """添加胜出的观测移除集，元素类型需可哈希、可排序。

    replica_id: 本副本标识，非空字符串。
    """

    def __init__(self, replica_id):
        if not isinstance(replica_id, str) or not replica_id:
            raise ValueError("replica_id must be a non-empty string")
        self.replica_id = replica_id
        # 副本标识 -> 已知最大序号，本副本因果历史的压缩表示
        self._clock = {}
        # 元素 -> 存活的加入点集合 {(replica_id, seq)}
        self._dots = {}
        # 元素 -> (被删的加入点 frozenset, 删除时刻的因果上下文 dict)
        self._tombs = {}
        # 副本标识 -> 该副本被观测到的时钟，用于判断墓碑是否全网可见
        self._known = {}
        self._touch()

    def _touch(self):
        self._known[self.replica_id] = dict(self._clock)

    def _bump(self):
        seq = self._clock.get(self.replica_id, 0) + 1
        self._clock[self.replica_id] = seq
        return seq

    def add(self, item):
        """加入元素，打上新的唯一加入点，返回自身。"""
        dot = (self.replica_id, self._bump())
        self._dots.setdefault(item, set()).add(dot)
        self._touch()
        return self

    def discard(self, item):
        """移除元素：把当前观测到的加入点转为墓碑，返回自身。"""
        dots = self._dots.pop(item, None)
        if dots:
            self._bump()
            old = self._tombs.get(item)
            if old:
                dots |= old[0]
            self._tombs[item] = (frozenset(dots), dict(self._clock))
            self._touch()
        return self

    def contains(self, item):
        """元素当前是否在集合里。"""
        return item in self._dots

    def value(self):
        """当前元素，按升序排列的元组。"""
        return tuple(sorted(self._dots))

    @staticmethod
    def _survives(dot, item, other):
        """本侧的点 dot 在对侧 other 的视角下是否存活。"""
        tomb = other._tombs.get(item)
        if tomb and dot in tomb[0]:
            return False
        if dot not in other._dots.get(item, ()) and other._clock.get(dot[0], 0) >= dot[1]:
            # 对侧见过这个点却不再持有：已被删除（墓碑可能已回收）
            return False
        return True

    def merge(self, other):
        """就地并入另一个副本，返回自身。合并满足交换律、结合律、幂等。"""
        if not isinstance(other, ORSet):
            raise TypeError("can only merge with ORSet")
        items = set(self._dots) | set(self._tombs) | set(other._dots) | set(other._tombs)
        dots = {}
        tombs = {}
        for item in items:
            live = {d for d in self._dots.get(item, ()) if self._survives(d, item, other)}
            live |= {d for d in other._dots.get(item, ()) if ORSet._survives(d, item, self)}
            if live:
                dots[item] = live
            gone = set()
            context = {}
            for side in (self, other):
                tomb = side._tombs.get(item)
                if tomb:
                    gone |= tomb[0]
                    context = _vv_max(context, tomb[1])
            if gone:
                tombs[item] = (frozenset(gone), context)
        self._dots = dots
        self._tombs = tombs
        self._clock = _vv_max(self._clock, other._clock)
        self._known[other.replica_id] = _vv_max(
            self._known.get(other.replica_id, {}), other._clock)
        for replica, clock in other._known.items():
            self._known[replica] = _vv_max(self._known.get(replica, {}), clock)
        self._touch()
        return self

    def gc(self):
        """回收所有已知副本都见过的墓碑，返回回收的个数。

        回收后已删元素不会复活：仍在路上、携带旧加入点的状态合并进来时，
        会被本副本的时钟挡下（点已被覆盖却无人持有，视为已删除）。
        """
        reclaimed = 0
        for item in list(self._tombs):
            context = self._tombs[item][1]
            if all(_vv_dominates(clock, context) for clock in self._known.values()):
                del self._tombs[item]
                reclaimed += 1
        return reclaimed

    def to_dict(self):
        """编码为纯标准数据类型（可直接 json.dumps 传输或落盘）。"""
        items = sorted(set(self._dots) | set(self._tombs), key=repr)
        return {
            "type": "ORSet",
            "version": 1,
            "replica": self.replica_id,
            "clock": {r: self._clock[r] for r in sorted(self._clock)},
            "adds": [
                [item, replica, seq]
                for item in items
                for replica, seq in sorted(self._dots.get(item, ()))
            ],
            "tombstones": [
                {
                    "item": item,
                    "dots": [[r, s] for r, s in sorted(self._tombs[item][0])],
                    "context": {r: self._tombs[item][1][r] for r in sorted(self._tombs[item][1])},
                }
                for item in items
                if item in self._tombs
            ],
            "known": {
                r: {k: self._known[r][k] for k in sorted(self._known[r])}
                for r in sorted(self._known)
            },
        }

    @classmethod
    def from_dict(cls, data):
        """从 to_dict() 的产物解码，往返不丢信息。"""
        if not isinstance(data, dict) or data.get("type") != "ORSet":
            raise ValueError("not an encoded ORSet")
        orset = cls(data["replica"])
        orset._clock = {str(r): int(s) for r, s in data["clock"].items()}
        orset._dots = {}
        for item, replica, seq in data["adds"]:
            orset._dots.setdefault(item, set()).add((replica, int(seq)))
        orset._tombs = {
            entry["item"]: (
                frozenset((r, int(s)) for r, s in entry["dots"]),
                {r: int(s) for r, s in entry["context"].items()},
            )
            for entry in data["tombstones"]
        }
        orset._known = {
            replica: {r: int(s) for r, s in clock.items()}
            for replica, clock in data["known"].items()
        }
        return orset

    def __repr__(self):
        return f"ORSet({self.replica_id!r}, {list(self.value())!r})"
