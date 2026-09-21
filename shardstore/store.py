"""分片键值表：键经哈希取模落到固定的若干分片上。

每片是一张独立的内存字典，各带一把重入锁。分片集合在建表时定死，之后
只读；同一个键在任何实例上都算出同一片（哈希带固定盐，不依赖 Python 的
进程随机哈希），所以没有中心协调也能本地算路由。
"""
import hashlib
import threading

SALT = b"shardstore"
_DIGEST_BYTES = 8


class ShardedKV:
    """键到分片的静态路由，外加各片独立的读写。

    shard_of() 只回答"这个键该在哪片"，put()/get()/delete() 在该片上读写，
    keys_in()/size()/distribution() 给出分布视图。分片顺序即槽位，改顺序
    会改变映射结果。
    """

    def __init__(self, shards):
        shards = list(shards)
        if not shards:
            raise ValueError("need at least one shard")
        if any(s is None or s == "" for s in shards):
            raise ValueError("shard id must be non-empty")
        if len(set(shards)) != len(shards):
            raise ValueError("duplicate shard id")
        self._shards = shards
        self._data = {s: {} for s in shards}
        self._locks = {s: threading.RLock() for s in shards}

    def shards(self):
        """返回全部 shard id 的副本，改它不影响映射。"""
        return list(self._shards)

    def __len__(self):
        return len(self._shards)

    def _slot(self, key):
        raw = key if isinstance(key, (bytes, bytearray)) else str(key).encode("utf-8")
        digest = hashlib.sha256(SALT + bytes(raw)).digest()
        return int.from_bytes(digest[:_DIGEST_BYTES], "big") % len(self._shards)

    def shard_of(self, key):
        """返回 key 落在的 shard id。同样的输入永远给同样的结果。"""
        return self._shards[self._slot(key)]

    def put(self, key, value):
        """写入 key，返回它落在的 shard id。"""
        shard = self.shard_of(key)
        with self._locks[shard]:
            self._data[shard][key] = value
        return shard

    def get(self, key, default=None):
        """读 key，不存在返回 default。"""
        shard = self.shard_of(key)
        with self._locks[shard]:
            return self._data[shard].get(key, default)

    def delete(self, key):
        """删除 key，删到了返回 True，本来就没有返回 False。"""
        shard = self.shard_of(key)
        with self._locks[shard]:
            if key in self._data[shard]:
                del self._data[shard][key]
                return True
            return False

    def keys_in(self, shard):
        """返回某片的全部 key（副本），顺序为写入顺序。"""
        if shard not in self._data:
            raise KeyError(shard)
        with self._locks[shard]:
            return list(self._data[shard])

    def size(self, shard):
        """某片的键条数。"""
        if shard not in self._data:
            raise KeyError(shard)
        with self._locks[shard]:
            return len(self._data[shard])

    def distribution(self):
        """各片条数 {shard: count}，空片计 0。"""
        return {s: self.size(s) for s in self._shards}

    def total(self):
        """全表键条数。"""
        return sum(self.size(s) for s in self._shards)
