"""分片键值表：键经哈希取模落到固定的若干分片上。

每片是一张独立的内存字典，各带一把重入锁。分片集合在建表时定死，之后
只读；同一个键在任何实例上都算出同一片（哈希带固定盐，不依赖 Python 的
进程随机哈希），所以没有中心协调也能本地算路由。

在线分裂：热片可以就地劈成两片，只有这一片里哈希到另一半区的键搬家，
别的片一个键不动。搬迁期间读先问新片、没有再回老片捞，写和删两片都落；
进度与断点持久化在 state_path，进程重启后从检查点接着搬。全部搬完才
允许提交：先把"已提交"落盘，再一次性换掉路由表，崩溃要么全成要么全退。
"""
import hashlib
import os
import pickle
import threading

SALT = b"shardstore"
_SPLIT_SALT = b"shardstore-split"
_DIGEST_BYTES = 8
_MAX_SPLITS = 256
_STATE_VERSION = 1


class ShardedKV:
    """键到分片的静态路由，外加各片独立的读写。

    shard_of() 只回答"这个键该在哪片"，put()/get()/delete() 在该片上读写，
    keys_in()/size()/distribution() 给出分布视图。分片顺序即槽位，改顺序
    会改变映射结果。

    分裂相关的入口：begin_split() 开刀，migrate_some()/migrate_all() 搬
    键，split_progress() 看进度，commit_split() 原子切换，abort_split()
    整体回滚。传了 state_path 时分裂状态落盘，重启后构造同一路径的实例
    自动恢复路由与断点。
    """

    def __init__(self, shards, state_path=None):
        shards = list(shards)
        if not shards:
            raise ValueError("need at least one shard")
        if any(s is None or s == "" for s in shards):
            raise ValueError("shard id must be non-empty")
        if len(set(shards)) != len(shards):
            raise ValueError("duplicate shard id")
        self._base = shards
        self._shards = list(shards)
        self._data = {s: {} for s in shards}
        self._locks = {s: threading.RLock() for s in shards}
        # 已提交的分裂：parent -> [(child, bit), ...]，按提交顺序。
        self._split_map = {}
        # 进行中的分裂：{"parent", "child", "bit", "moved"}，同时只有一个。
        self._active = None
        self._next_bit = 0
        self._split_lock = threading.RLock()
        self._state_path = state_path
        if state_path is not None and os.path.exists(state_path):
            self._recover()

    def shards(self):
        """返回全部 shard id 的副本，改它不影响映射。"""
        return list(self._shards)

    def __len__(self):
        return len(self._shards)

    @staticmethod
    def _raw(key):
        if isinstance(key, (bytes, bytearray)):
            return bytes(key)
        return str(key).encode("utf-8")

    def _slot(self, key):
        digest = hashlib.sha256(SALT + self._raw(key)).digest()
        return int.from_bytes(digest[:_DIGEST_BYTES], "big") % len(self._base)

    def _split_bit(self, key, bit):
        digest = hashlib.sha256(_SPLIT_SALT + self._raw(key)).digest()
        return (digest[bit // 8] >> (bit % 8)) & 1

    def shard_of(self, key):
        """返回 key 落在的 shard id。同样的输入永远给同样的结果。

        先按建表时的片集合取模，再沿已提交的分裂记录逐位下钻；进行中的
        分裂不影响路由，提交前键永远还指在老片上。
        """
        shard = self._base[self._slot(key)]
        split_map = self._split_map
        while shard in split_map:
            nxt = None
            for child, bit in split_map[shard]:
                if self._split_bit(key, bit):
                    nxt = child
                    break
            if nxt is None:
                break
            shard = nxt
        return shard

    def _in_transit(self, key, shard):
        """key 属于正在搬迁的那一半时返回新片 id，否则返回 None。"""
        active = self._active
        if active is not None and shard == active["parent"]:
            if self._split_bit(key, active["bit"]):
                return active["child"]
        return None

    def put(self, key, value):
        """写入 key，返回它落在的 shard id。分裂中目标半区双写两片。"""
        shard = self.shard_of(key)
        transit = self._in_transit(key, shard)
        if transit is not None:
            with self._locks[shard]:
                self._data[shard][key] = value
                with self._locks[transit]:
                    self._data[transit][key] = value
            return shard
        with self._locks[shard]:
            self._data[shard][key] = value
        return shard

    def get(self, key, default=None):
        """读 key，不存在返回 default。分裂中先问新片，没有再回老片。"""
        shard = self.shard_of(key)
        transit = self._in_transit(key, shard)
        if transit is not None:
            with self._locks[transit]:
                if key in self._data[transit]:
                    return self._data[transit][key]
        with self._locks[shard]:
            return self._data[shard].get(key, default)

    def delete(self, key):
        """删除 key，删到了返回 True，本来就没有返回 False。分裂中两片都删。"""
        shard = self.shard_of(key)
        transit = self._in_transit(key, shard)
        if transit is not None:
            hit = False
            with self._locks[shard]:
                if key in self._data[shard]:
                    del self._data[shard][key]
                    hit = True
                with self._locks[transit]:
                    if key in self._data[transit]:
                        del self._data[transit][key]
                        hit = True
            return hit
        with self._locks[shard]:
            if key in self._data[shard]:
                del self._data[shard][key]
                return True
            return False

    def _register_child(self, child):
        self._shards.append(child)
        self._data[child] = {}
        self._locks[child] = threading.RLock()

    def begin_split(self, parent, child):
        """把 parent 就地劈成两片，新片 child 诞生并开始搬迁。

        只登记状态和空新片，不搬键；同一时刻只允许一个分裂在进行。
        """
        with self._split_lock:
            if parent not in self._data:
                raise KeyError(parent)
            if child is None or child == "":
                raise ValueError("shard id must be non-empty")
            if child in self._data:
                raise ValueError("duplicate shard id")
            if self._active is not None:
                raise RuntimeError("another split is already in progress")
            if self._next_bit >= _MAX_SPLITS:
                raise RuntimeError("split bit budget exhausted")
            self._register_child(child)
            self._active = {"parent": parent, "child": child,
                            "bit": self._next_bit, "moved": set()}
            self._next_bit += 1
            self._persist()
            return child

    def splitting(self):
        """进行中的分裂 (parent, child)，没有返回 None。"""
        active = self._active
        if active is None:
            return None
        return (active["parent"], active["child"])

    def split_progress(self):
        """分裂进度 {"parent", "child", "moved", "remaining", "total"}。

        moved 是已搬进新片的键数，remaining 是老片里还等着搬的键数；
        没有分裂在进行时返回 None。
        """
        active = self._active
        if active is None:
            return None
        parent, bit, moved = active["parent"], active["bit"], active["moved"]
        with self._locks[parent]:
            remaining = sum(1 for k in self._data[parent]
                            if k not in moved and self._split_bit(k, bit))
        return {"parent": parent, "child": active["child"],
                "moved": len(moved), "remaining": remaining,
                "total": len(moved) + remaining}

    def migrate_some(self, n):
        """最多搬 n 个键进新片，返回本次实际搬了几个。老片保留副本到提交。"""
        with self._split_lock:
            active = self._active
            if active is None:
                raise RuntimeError("no split in progress")
            if n <= 0:
                return 0
            parent = active["parent"]
            child = active["child"]
            bit = active["bit"]
            moved = active["moved"]
            count = 0
            with self._locks[parent]:
                with self._locks[child]:
                    for key, value in list(self._data[parent].items()):
                        if count >= n:
                            break
                        if key in moved or not self._split_bit(key, bit):
                            continue
                        self._data[child][key] = value
                        moved.add(key)
                        count += 1
            self._persist()
            return count

    def migrate_all(self, batch=256):
        """按 batch 一批批搬完，返回搬键总数；每批落一次检查点。"""
        total = 0
        while True:
            moved = self.migrate_some(batch)
            total += moved
            if moved == 0:
                return total

    def commit_split(self):
        """原子切换：先落盘"已提交"，再一次性换路由表，最后清老片副本。

        崩溃只可能发生在落盘前（分裂不算数，老片数据完整）或落盘后
        （重启按已提交的路由恢复），不存在半新半旧。
        """
        with self._split_lock:
            active = self._active
            if active is None:
                raise RuntimeError("no split in progress")
            if self.split_progress()["remaining"]:
                raise RuntimeError("migration not complete")
            parent, child, bit = active["parent"], active["child"], active["bit"]
            new_map = {p: list(entries) for p, entries in self._split_map.items()}
            new_map.setdefault(parent, []).append((child, bit))
            self._split_map = new_map
            self._active = None
            self._persist()
            with self._locks[parent]:
                for key in [k for k in self._data[parent]
                            if self._split_bit(k, bit)]:
                    del self._data[parent][key]
            return child

    def abort_split(self):
        """整体回滚：老片在提交前始终持有全量键，弃掉新片即全退。"""
        with self._split_lock:
            active = self._active
            if active is None:
                raise RuntimeError("no split in progress")
            child = active["child"]
            self._active = None
            self._shards.remove(child)
            del self._data[child]
            del self._locks[child]
            self._persist()

    def _persist(self):
        """把分裂状态原子写进 state_path（临时文件 + os.replace）。"""
        if self._state_path is None:
            return
        active = None
        if self._active is not None:
            child = self._active["child"]
            journal = {k: self._data[child][k]
                       for k in self._active["moved"] if k in self._data[child]}
            active = {"parent": self._active["parent"], "child": child,
                      "bit": self._active["bit"], "journal": journal}
        state = {"version": _STATE_VERSION,
                 "base": list(self._base),
                 "next_bit": self._next_bit,
                 "splits": {p: list(entries)
                            for p, entries in self._split_map.items()},
                 "active": active}
        tmp = self._state_path + ".tmp"
        with open(tmp, "wb") as fh:
            pickle.dump(state, fh)
        os.replace(tmp, self._state_path)

    def _recover(self):
        """从 state_path 恢复：已提交的分裂恢复路由，未完成的恢复断点。"""
        with open(self._state_path, "rb") as fh:
            state = pickle.load(fh)
        if state.get("version") != _STATE_VERSION or state.get("base") != self._base:
            raise ValueError("split state does not match this shard set")
        self._next_bit = state["next_bit"]
        for entries in state["splits"].values():
            for child, _bit in entries:
                self._register_child(child)
        self._split_map = {p: list(entries)
                           for p, entries in state["splits"].items()}
        active = state["active"]
        if active is not None:
            self._register_child(active["child"])
            self._data[active["child"]].update(active["journal"])
            self._active = {"parent": active["parent"],
                            "child": active["child"],
                            "bit": active["bit"],
                            "moved": set(active["journal"])}

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
