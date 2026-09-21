"""分片账本。

Ledger 把每个分片对应到一个 ExactCounter：各片自己给自己去重，
total() 把各片的 count 直接相加。跨片重复的 key 会被数进去多次，
所以 total() 只在分片互不重叠时才等于并集大小。
"""

from dedupkit.exact import ExactCounter


class Ledger:
    """按分片记账的去重账本。分片名必须是 str。"""

    def __init__(self):
        self._shards = {}

    def add(self, shard, key):
        """往某个分片记一个 key，分片不存在就新建；返回是否首次出现。"""
        if not isinstance(shard, str):
            raise TypeError(f"分片名必须是 str，收到 {type(shard).__name__}")
        counter = self._shards.get(shard)
        if counter is None:
            counter = ExactCounter()
            self._shards[shard] = counter
        return counter.add(key)

    def count(self, shard):
        """某个分片内的不同 key 数；分片不存在抛 KeyError。"""
        return self._shards[shard].count()

    def keys(self, shard):
        """某个分片内 key 的快照；分片不存在抛 KeyError。"""
        return self._shards[shard].keys()

    def total(self):
        """各片 count 的直接相加；跨片重复的 key 会被重复计入。"""
        return sum(counter.count() for counter in self._shards.values())

    def names(self):
        """分片名，按字典序排好，方便稳定落盘。"""
        return tuple(sorted(self._shards))
