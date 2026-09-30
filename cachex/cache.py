"""固定容量的键值缓存，纯标准库，无外部依赖。

现有能力（基线）：

- 构造只要一个容量，容量是条目的最大条数，正整数，小于一在构造处当场拒绝；
- 内部只有一个字典装着全部条目，每条另记一个自增序号表示最近一次使用；
- get 命中返回值并把该条的序号刷成新的最大，未命中返回 None；
- put 写新键，同样给一个新的最大序号；
- 键已经存在时 put 只覆盖值，不改变它的使用次序；长度为零的键在入口处拒绝；
- 容量满时先扫一遍全部条目，逐条比较挑出使用序号最小也就是最久未使用的那条
  丢掉，再把新键放进去；
- keys 报当前条目键，按使用序号从最久未使用到最近使用排列；
- stats 给出容量、条目数、命中、未命中与淘汰数。

每次淘汰都遍历全部条目逐一比较，条目一多就慢；缓存里只有最久未使用这一种挑法，
没有频次口径，没有先进先出的先后口径，也没有过期时间。
"""

_CAPACITY_ERROR = "capacity must be a positive integer"


class CacheError(Exception):
    """缓存错误的基类：容量非法与空键都从这里派生。"""


class InvalidCapacityError(CacheError):
    """容量不是正整数。"""


class InvalidKeyError(CacheError):
    """键为空。"""


class Cache:
    """固定容量的缓存。

    capacity 是条目数上限；淘汰挑最久未使用的条目，即使用序号最小的那条。
    """

    def __init__(self, capacity):
        if not isinstance(capacity, int) or isinstance(capacity, bool) or capacity < 1:
            raise InvalidCapacityError(_CAPACITY_ERROR)
        self.capacity = capacity
        self._entries = {}
        self._tick = 0
        self._hits = 0
        self._misses = 0
        self._evicted = 0

    def _next_tick(self):
        self._tick += 1
        return self._tick

    def get(self, key):
        """命中返回值并把使用次序刷成最近；未命中返回 None 并记一次未命中。"""
        entry = self._entries.get(key)
        if entry is None:
            self._misses += 1
            return None
        entry["used"] = self._next_tick()
        self._hits += 1
        return entry["value"]

    def put(self, key, value):
        """写入键值。已有键只覆盖值；新键在满容量时先淘汰最久未使用的一条。"""
        if key == "":
            raise InvalidKeyError("key must not be empty")
        entry = self._entries.get(key)
        if entry is not None:
            entry["value"] = value
            return
        if len(self._entries) >= self.capacity:
            self._evict_one()
        self._entries[key] = {"value": value, "used": self._next_tick()}

    def _evict_one(self):
        """淘汰一条：扫遍全部条目，逐条比较使用序号，挑最小的那条丢掉。"""
        if not self._entries:
            return
        victim = None
        victim_used = None
        for key, entry in self._entries.items():
            if victim_used is None or entry["used"] < victim_used:
                victim = key
                victim_used = entry["used"]
        del self._entries[victim]
        self._evicted += 1

    def peek(self, key):
        """只取值，不动使用次序，不记统计；键不存在返回 None。"""
        entry = self._entries.get(key)
        return None if entry is None else entry["value"]

    def __contains__(self, key):
        return key in self._entries

    def __len__(self):
        return len(self._entries)

    def keys(self):
        """当前条目键，按最久未使用到最近使用排列。"""
        return sorted(self._entries, key=lambda k: self._entries[k]["used"])

    def stats(self):
        """统计快照，独立 dict。"""
        return {
            "capacity": self.capacity,
            "size": len(self._entries),
            "hits": self._hits,
            "misses": self._misses,
            "evicted": self._evicted,
        }
