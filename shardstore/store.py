"""分片键值表：键经哈希取模落到固定的若干分片上，并支持在线分裂单分片。

每片是一张独立的内存字典，各带一把重入锁。初始分片集合在建表时定死；
同一个键在任何实例上都算出同一片（哈希带固定盐，不依赖 Python 的进程随机
哈希），所以没有中心协调也能本地算路由。

在线分裂不动别的片：某片沿哈希位对半劈成两片，老片收窄到一半，新片接走
另一半。分裂进行中读先问新片再回退老片、写两边都落；游标持久化在状态文件
里，进程重启可从断点续搬；两边数据对账一致后一次性提交钉死路由，也可以
整体回退。
"""
import contextlib
import hashlib
import json
import os
import tempfile
import threading

SALT = b"shardstore"
_DIGEST_BYTES = 8
_DIGEST_BITS = _DIGEST_BYTES * 8
_STATE_VERSION = 1


def _digest(key):
    """键的稳定 64 位摘要：加盐 sha256 前 8 字节，不依赖进程随机哈希。"""
    raw = key if isinstance(key, (bytes, bytearray)) else str(key).encode("utf-8")
    digest = hashlib.sha256(SALT + bytes(raw)).digest()
    return int.from_bytes(digest[:_DIGEST_BYTES], "big")


def _fits(digest, bucket_count, desc):
    """digest 是否命中文案 (bucket, mask, want)：模 N 落桶且掩码位全对。"""
    bucket, mask, want = desc
    return digest % bucket_count == bucket and (digest & mask) == want


def _mask_depth(mask):
    """分裂掩码里已经钉了多少个哈希位。"""
    return bin(mask).count("1")


def _encode_key(key):
    """把键编码成可 JSON 持久化的形态（快照、游标里用）。"""
    if isinstance(key, bytes):
        return {"t": "b", "hex": key.hex()}
    if isinstance(key, int):
        return {"t": "i", "v": key}
    return {"t": "s", "v": str(key)}


def _decode_key(rec):
    kind = rec["t"]
    if kind == "b":
        return bytes.fromhex(rec["hex"])
    if kind == "i":
        return rec["v"]
    return rec["v"]


class _Routing:
    """某一时刻的不可变路由快照，换路由就是整体换对象（带 epoch）。"""

    def __init__(self, shards, desc, bucket_count, mig=None, epoch=0):
        self.shards = list(shards)
        self.desc = dict(desc)
        self.bucket_count = bucket_count
        self.mig = mig
        self.epoch = epoch

    def plan_for(self, digest):
        """返回 (属主片id, 迁移中的新片id或None)。

        分裂中：新片描述子更窄，命中它的键属主是新片（老片描述子仍覆盖
        整个旧范围，所以先判迁移目标）；其余键仍归老片。
        """
        mig = self.mig
        if mig is not None:
            new = mig["new"]
            if _fits(digest, self.bucket_count, self.desc[new]):
                return new, new
            old = mig["old"]
            if _fits(digest, self.bucket_count, self.desc[old]):
                return old, None
        for shard in self.shards:
            if _fits(digest, self.bucket_count, self.desc[shard]):
                return shard, None
        raise AssertionError("no shard owns key")  # 描述子应始终完整覆盖


class ShardedKV:
    """键到分片的路由，外加各片独立的读写与在线分裂。

    shard_of() 只回答"这个键现在在哪片"，put()/get()/delete() 按当前路由
    读写，keys_in()/size()/distribution() 给出分布视图。state_path 给定时
    分裂拓扑与搬运游标持久化到该文件，构造时若文件存在则从断点恢复。
    """

    def __init__(self, shards, state_path=None):
        shards = list(shards)
        if not shards:
            raise ValueError("need at least one shard")
        if any(s is None or s == "" for s in shards):
            raise ValueError("shard id must be non-empty")
        if len(set(shards)) != len(shards):
            raise ValueError("duplicate shard id")
        self._state_path = state_path
        self._topo_lock = threading.RLock()
        self._data = {s: {} for s in shards}
        self._locks = {s: threading.RLock() for s in shards}
        if state_path and os.path.exists(state_path):
            self._routing = self._load_state(shards)
        else:
            n = len(shards)
            desc = {s: (i, 0, 0) for i, s in enumerate(shards)}
            self._routing = _Routing(shards, desc, n)
            self._persist()

    # ---------- 基础视图 ----------

    def shards(self):
        """返回全部 shard id 的副本，改它不影响映射。"""
        return list(self._routing.shards)

    def __len__(self):
        return len(self._routing.shards)

    def shard_of(self, key):
        """返回 key 当前落在的 shard id。同样的输入永远给同样的结果。"""
        routing = self._routing
        owner, _ = routing.plan_for(_digest(key))
        return owner

    @contextlib.contextmanager
    def _locked(self, routing, names):
        """按 shard 在路由里的槽位顺序取锁；换过路由就抛 RuntimeError。

        分裂提交要换整片描述子，读者/写者必须持有的是新路由的快照，否则
        可能在切换瞬间按老路由落写而两边都漏。统一顺序取锁也避免双写时
        与搬移线程互锁。
        """
        ordered = sorted(set(names), key=routing.shards.index)
        acquired = []
        try:
            for name in ordered:
                self._locks[name].acquire()
                acquired.append(name)
            if self._routing is not routing:
                raise RuntimeError("routing changed while acquiring shard locks")
            yield
        finally:
            for name in reversed(acquired):
                self._locks[name].release()

    def put(self, key, value):
        """写入 key，返回它当前属主的 shard id。

        分裂进行中且键属于被搬走的一半：两边都落，老片那份保证读回退和
        搬运对账都还能看到，直到提交那一刻。
        """
        while True:
            routing = self._routing
            owner, moving = routing.plan_for(_digest(key))
            targets = [owner, routing.mig["old"]] if moving is not None else [owner]
            try:
                with self._locked(routing, targets):
                    for name in targets:
                        self._data[name][key] = value
                return owner
            except RuntimeError:
                continue

    def get(self, key, default=None):
        """读 key：分裂中先问新片，没有再回退老片捞；其余直接读属主片。"""
        while True:
            routing = self._routing
            owner, moving = routing.plan_for(_digest(key))
            try:
                if moving is not None:
                    old = routing.mig["old"]
                    with self._locked(routing, [owner, old]):
                        if key in self._data[owner]:
                            return self._data[owner][key]
                        return self._data[old].get(key, default)
                with self._locked(routing, [owner]):
                    return self._data[owner].get(key, default)
            except RuntimeError:
                continue

    def delete(self, key):
        """删除 key，删到了返回 True，本来就没有返回 False。

        分裂中键属于搬走的一半时，新片和老片两份一起删，避免提交对账时
        老片里冒出一个搬过去后才删掉的键。
        """
        while True:
            routing = self._routing
            owner, moving = routing.plan_for(_digest(key))
            targets = [owner, routing.mig["old"]] if moving is not None else [owner]
            try:
                with self._locked(routing, targets):
                    hit = False
                    for name in targets:
                        table = self._data[name]
                        if key in table:
                            del table[key]
                            hit = True
                    return hit
            except RuntimeError:
                continue

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
        """各片条数 {shard: count}，空片计 0（分裂中含两边重叠的副本）。"""
        return {s: self.size(s) for s in self._routing.shards}

    def total(self):
        """全表键条数。"""
        return sum(self.size(s) for s in self._routing.shards)

    # ---------- 在线分裂 ----------

    def begin_split(self, shard, new_shard, batch_size=100):
        """就地把 shard 沿下一个哈希位劈成两片，立刻进入在线搬移阶段。

        shard 收窄到该位为 0 的一半，new_shard 接走该位为 1 的一半；别片
        一个键不动。起点快照（分裂开始时老片的键列表）固定下来作为游标
        与对账依据，之后新写入的键走读写路径的双写。
        """
        with self._topo_lock:
            routing = self._routing
            if routing.mig is not None:
                raise RuntimeError("a split is already in progress")
            if shard not in routing.desc:
                raise KeyError(shard)
            if new_shard in routing.desc:
                raise ValueError("shard id already exists: %r" % (new_shard,))
            if new_shard is None or new_shard == "":
                raise ValueError("shard id must be non-empty")
            bucket, mask, want = routing.desc[shard]
            depth = _mask_depth(mask)
            if depth >= _DIGEST_BITS - 1:
                raise RuntimeError("no more hash bits to split")
            bit = 1 << (_DIGEST_BITS - 1 - depth)

            with self._locks[shard]:
                snapshot = list(self._data[shard])

            half_total = sum(1 for k in snapshot if _digest(k) & bit)

            shards = routing.shards + [new_shard]
            desc = dict(routing.desc)
            desc[shard] = (bucket, mask | bit, want)
            desc[new_shard] = (bucket, mask | bit, want | bit)
            mig = {
                "old": shard,
                "new": new_shard,
                "bit": bit,
                "old_mask": mask,
                "old_want": want,
                "snapshot": [_encode_key(k) for k in snapshot],
                "cursor": 0,
                "moved": 0,
                "half_total": half_total,
                "batch_size": batch_size,
            }
            self._data[new_shard] = {}
            self._locks[new_shard] = threading.RLock()
            self._routing = _Routing(shards, desc, routing.bucket_count,
                                     mig=mig, epoch=routing.epoch + 1)
            self._persist()
            return self.split_progress()

    def migrate_batch(self):
        """顺着快照游标再搬一批属于新片的键，返回本批实际拷过去的条数。

        游标每走完一批就落盘，崩溃重启后从断点接着扫，扫过的不重扫；
        拷贝是 at-least-once，重复键直接覆盖成同值，不产生脏数据。
        """
        with self._topo_lock:
            routing = self._routing
            mig = routing.mig
            if mig is None:
                raise RuntimeError("no split in progress")
            old, new = mig["old"], mig["new"]
            bit = mig["bit"]
            snapshot = mig["snapshot"]
            cursor = mig["cursor"]
            if cursor >= len(snapshot):
                return 0
            end = min(cursor + mig["batch_size"], len(snapshot))
            copied = 0
            with self._locked(routing, [new, old]):
                for i in range(cursor, end):
                    key = _decode_key(snapshot[i])
                    if not (_digest(key) & bit):
                        continue  # 留在老片的一半，不搬
                    if key not in self._data[old]:
                        continue  # 快照之后被删
                    self._data[new][key] = self._data[old][key]
                    copied += 1
            mig["cursor"] = end
            mig["moved"] += copied
            self._persist()
            return copied

    def migrate_until_done(self):
        """连续搬完整个快照，返回总搬运批次数（每批都落进度）。"""
        batches = 0
        while self.migrate_batch() > 0:
            batches += 1
        return batches

    def _reconcile(self, routing):
        """持新、老两把锁对账：该搬的两边都在且同值，新片没有来路不明的键。"""
        mig = routing.mig
        old, new = mig["old"], mig["new"]
        bit = mig["bit"]
        old_table = self._data[old]
        new_table = self._data[new]

        for rec in mig["snapshot"]:
            key = _decode_key(rec)
            if not (_digest(key) & bit) or key not in old_table:
                continue  # 留在老片的一半，或分裂后删掉的键
            if key not in new_table or new_table[key] != old_table[key]:
                raise RuntimeError("split not caught up: %r" % (key,))
        for key in new_table:
            if not (_digest(key) & bit):
                raise RuntimeError("stray key on new shard: %r" % (key,))
            if key not in old_table:
                raise RuntimeError("orphan key on new shard: %r" % (key,))

    def commit_split(self):
        """对账一致后一次性钉死路由：清老片副本、提交拓扑。

        状态文件先原子写成 committed（此刻新片已什么都不缺），再换内存
        路由指针并清老片副本；任一步崩溃，重启都按已提交状态重建，不会
        出现半新半旧的路由。没搬完直接报错，绝不提前切指针。
        """
        with self._topo_lock:
            routing = self._routing
            mig = routing.mig
            if mig is None:
                raise RuntimeError("no split in progress")
            if mig["cursor"] < len(mig["snapshot"]):
                raise RuntimeError("migration not finished: %d/%d scanned"
                                   % (mig["cursor"], len(mig["snapshot"])))
            with self._locked(routing, [mig["new"], mig["old"]]):
                old, new = mig["old"], mig["new"]
                bit = mig["bit"]
                self._catch_up(routing)
                self._reconcile(routing)
                committed = _Routing(routing.shards, routing.desc,
                                     routing.bucket_count, epoch=routing.epoch + 1)
                self._persist(committed)
                for key in list(self._data[old]):
                    if _digest(key) & bit:
                        del self._data[old][key]
                self._routing = committed
            return self.shards()

    def _catch_up(self, routing):
        """提交前在锁内做最终追平：老片里该搬的键全部同步到新片最新值。

        游标扫描之后才落到老片的写入（双写覆盖了它们，崩溃重启丢过内存
        副本时同理）由这一遍兜底，保证提交瞬间新片不缺键、值不旧。
        """
        mig = routing.mig
        old, new, bit = mig["old"], mig["new"], mig["bit"]
        for key, value in list(self._data[old].items()):
            if _digest(key) & bit:
                self._data[new][key] = value

    def rollback_split(self):
        """整体回退当前分裂：丢弃新片，路由退回只有老片的旧拓扑。

        老片在整个迁移期间始终保留全量副本（写双落、读回退），所以回退
        不需要补数据；先落回退状态再换指针，崩溃重启仍是旧拓扑。
        """
        with self._topo_lock:
            routing = self._routing
            mig = routing.mig
            if mig is None:
                raise RuntimeError("no split in progress")
            old, new = mig["old"], mig["new"]
            with self._locked(routing, [new, old]):
                desc = {s: routing.desc[s] for s in routing.shards if s != new}
                bucket = routing.desc[old][0]
                desc[old] = (bucket, mig["old_mask"], mig["old_want"])  # 老片恢复整段
                shards = [s for s in routing.shards if s != new]
                rolled_back = _Routing(shards, desc, routing.bucket_count,
                                       epoch=routing.epoch + 1)
                self._persist(rolled_back)  # 先落盘，再动内存指针
                self._routing = rolled_back
            del self._data[new]
            del self._locks[new]
            return self.shards()

    def split_progress(self):
        """当前分裂的进度视图；没有分裂在进行时返回 None。"""
        routing = self._routing
        mig = routing.mig
        if mig is None:
            return None
        scanned = mig["cursor"]
        return {
            "old": mig["old"],
            "new": mig["new"],
            "scanned": scanned,
            "snapshot_size": len(mig["snapshot"]),
            "moved": mig["moved"],
            "half_total": mig["half_total"],
            "remaining_snapshot": len(mig["snapshot"]) - scanned,
            "done": scanned >= len(mig["snapshot"]),
        }

    # ---------- 持久化与断点恢复 ----------

    def _state_payload(self, routing):
        return {
            "version": _STATE_VERSION,
            "bucket_count": routing.bucket_count,
            "shards": [[s] + list(routing.desc[s]) for s in routing.shards],
            "migrating": routing.mig,
        }

    def _persist(self, routing=None):
        """把当前（或指定）路由+游标原子落盘：临时文件写完再 rename。"""
        if not self._state_path:
            return
        routing = routing if routing is not None else self._routing
        directory = os.path.dirname(os.path.abspath(self._state_path))
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".shardstate-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(self._state_payload(routing), handle,
                          ensure_ascii=False, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self._state_path)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    def _load_state(self, base_shards):
        """从状态文件重建路由；分裂没收尾则带着游标接着搬。"""
        with open(self._state_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if payload.get("version") != _STATE_VERSION:
            raise ValueError("unsupported state version: %r" % (payload.get("version"),))
        bucket_count = payload["bucket_count"]
        shards = [entry[0] for entry in payload["shards"]]
        desc = {entry[0]: (entry[1], entry[2], entry[3]) for entry in payload["shards"]}
        for name in base_shards:
            if name not in desc:
                raise ValueError("state file has no shard %r" % (name,))
        for name in shards:
            self._data.setdefault(name, {})
            self._locks.setdefault(name, threading.RLock())
        mig = payload.get("migrating")
        if mig is not None:
            mig = dict(mig)  # 游标、快照原样恢复，从断点继续
        return _Routing(shards, desc, bucket_count, mig=mig)
