"""分片键值表：键经哈希取模落到固定的若干分片上。

每片是一张独立的内存字典，各带一把重入锁。分片集合在建表时定死；同一
个键在任何实例上都算出同一片（哈希带固定盐，不依赖 Python 的进程随机
哈希），所以没有中心协调也能本地算路由。

在线分裂：begin_split() 给某片挂一张影子新片，分裂期间路由仍按已提交
拓扑走老片——读先问新片、没有再回老片捞；判定搬去新片的键写两边，其
余只写老片。migrate() 分批把键交给新片，游标写检查点，进程重启后
open() 从断点接着搬。commit() 在两锁清空残键后一次性原子换路由，
abort() 合回老片整体回退，其它片全程一个键都不动。
"""
import base64
import hashlib
import json
import os
import threading

SALT = b"shardstore"
_DIGEST_BYTES = 8

_MANIFEST = "manifest.json"
_WAL = "wal.log"
_CHECKPOINT = "split.cp.json"


def _hash(key):
    raw = key if isinstance(key, (bytes, bytearray)) else str(key).encode("utf-8")
    digest = hashlib.sha256(SALT + bytes(raw)).digest()
    return int.from_bytes(digest[:_DIGEST_BYTES], "big")


def _encode_key(key):
    if isinstance(key, str):
        return ["s", key]
    if isinstance(key, bytes):
        return ["b", base64.b64encode(key).decode("ascii")]
    if isinstance(key, bool) or isinstance(key, int):
        return ["i", int(key)]
    raise TypeError("keys must be str, bytes or int")


def _decode_key(token):
    kind, payload = token
    if kind == "s":
        return payload
    if kind == "b":
        return base64.b64decode(payload)
    if kind == "i":
        return payload
    raise ValueError("bad key token %r" % (token,))


def _encode_value(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (bytes, bytearray)):
        return {"__bytes__": base64.b64encode(bytes(value)).decode("ascii")}
    if isinstance(value, list):
        return [_encode_value(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _encode_value(v) for k, v in value.items()}
    raise TypeError("value of %r is not storable" % (type(value),))


def _decode_value(value):
    if isinstance(value, list):
        return [_decode_value(item) for item in value]
    if isinstance(value, dict):
        if set(value) == {"__bytes__"}:
            return base64.b64decode(value["__bytes__"])
        return {k: _decode_value(v) for k, v in value.items()}
    return value


class SplitOperation:
    """一次进行中的分裂：老片 old 劈出影子新片 new。

    老片的路由记录是 (m, b)；本域键满足 h % m == b，其中
    h % 2m == b+m 的搬去新片，h % 2m == b 的留在老片。done 是至少
    交接过一次的键游标，落检查点，重启不重搬。
    """

    def __init__(self, kv, old, new, modulus, base, done=None):
        self._kv = kv
        self.old = old
        self.new = new
        self._m = modulus
        self._b = base
        self.done = set(done or ())
        self.data = {}
        self.lock = threading.RLock()
        self.state = "migrating"

    def _mover_hash(self, h):
        return h % (2 * self._m) == self._b + self._m

    def _live(self):
        if self._kv is None or self.state != "migrating":
            raise RuntimeError("split is no longer active")
        return self._kv

    def is_mover(self, key):
        """key 是否属于要搬去新片的那一半。"""
        self._live()
        return self._mover_hash(_hash(key))

    def migrate(self, limit=128):
        """搬一批键去新片，返回这一批实际交接的条数；limit=None 搬一批。"""
        return self._live()._split_migrate(self, limit)

    def drain(self):
        """反复搬，直到老片里没有未交接过的待搬键，返回累计交接条数。"""
        kv = self._live()
        moved_total = 0
        while True:
            moved = kv._split_migrate(self, None)
            moved_total += moved
            if not moved:
                return moved_total

    def progress(self):
        """搬了多少、还剩多少：moved/remaining/total/fraction。"""
        return self._live()._split_progress(self)

    def new_size(self):
        """新片目前有多少键（含双写预放的）。"""
        self._live()
        with self.lock:
            return len(self.data)

    def keys_new(self):
        """新片目前的全部键（副本）。"""
        self._live()
        with self.lock:
            return list(self.data)

    def commit(self):
        """搬净残键后原子提交：换路由、新片转正，返回新片 id。"""
        return self._live()._split_commit(self)

    def abort(self):
        """整体回退：新片合回老片，路由保持分裂前原样，返回老片 id。"""
        return self._live()._split_abort(self)


class ShardedKV:
    """键到分片的静态路由，外加各片独立的读写。

    shard_of() 只回答"这个键该在哪片"，put()/get()/delete() 在该片上
    读写，keys_in()/size()/distribution() 给出分布视图。分裂通过
    begin_split()/active_split() 驱动；传 state_dir 后写操作先落 WAL
    （fsync），分裂游标落检查点，open() 在进程重启后续搬。
    """

    def __init__(self, shards, state_dir=None):
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
        modulus = len(shards)
        self._records = [(modulus, i, s) for i, s in enumerate(shards)]
        self._split = None
        self._commit_lock = threading.RLock()
        self._wal_lock = threading.Lock()
        self._wal_fh = None
        self._dir = state_dir
        if state_dir is not None:
            if os.path.exists(os.path.join(state_dir, _MANIFEST)):
                raise ValueError("state_dir already in use; call ShardedKV.open()")
            os.makedirs(state_dir, exist_ok=True)
            if os.listdir(state_dir):
                raise ValueError("state_dir must be empty")
            self._write_snapshot("snapshot.1.json", self._records, self._shards)
            self._persist_manifest("snapshot.1.json", self._records, self._shards)

    @classmethod
    def open(cls, state_dir):
        """从 state_dir 重建实例；有未完成分裂则挂回并回放 WAL 续上。"""
        manifest_path = os.path.join(state_dir, _MANIFEST)
        with open(manifest_path, "r", encoding="utf-8") as fh:
            manifest = json.load(fh)
        shards = [_decode_key(token) for token in manifest["shards"]]
        records = [(m, b, _decode_key(token)) for m, b, token in manifest["records"]]

        kv = cls.__new__(cls)
        kv._shards = shards
        kv._data = {s: {} for s in shards}
        kv._locks = {s: threading.RLock() for s in shards}
        kv._records = records
        kv._split = None
        kv._commit_lock = threading.RLock()
        kv._wal_lock = threading.Lock()
        kv._wal_fh = None
        kv._dir = state_dir

        with open(os.path.join(state_dir, manifest["snapshot"]), "r",
                  encoding="utf-8") as fh:
            snapshot = json.load(fh)
        for item in snapshot["data"]:
            shard = _decode_key(item["shard"])
            bucket = kv._data[shard]
            for pair in item["items"]:
                bucket[_decode_key(pair[0])] = _decode_value(pair[1])

        active_split = None
        checkpoint_path = os.path.join(state_dir, _CHECKPOINT)
        if os.path.exists(checkpoint_path):
            with open(checkpoint_path, "r", encoding="utf-8") as fh:
                checkpoint = json.load(fh)
            target = _decode_key(checkpoint["target"])
            if target in shards:
                # 提交已原子翻转（manifest 含新片），只差删检查点这一步。
                # 新快照是权威状态，旧 WAL（含 mv）整段作废，不能再回放。
                os.remove(checkpoint_path)
                wal_path = os.path.join(state_dir, _WAL)
                if os.path.exists(wal_path):
                    os.remove(wal_path)
                kv._fsync_dir()
            else:
                active_split = SplitOperation(
                    kv,
                    _decode_key(checkpoint["old"]),
                    target,
                    checkpoint["m"],
                    checkpoint["b"],
                    done=[_decode_key(token) for token in checkpoint["done"]],
                )
                kv._split = active_split
                kv._locks[target] = active_split.lock

        wal_path = os.path.join(state_dir, _WAL)
        if os.path.exists(wal_path):
            with open(wal_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        kv._replay_entry(json.loads(line), active_split)
            if active_split is not None:
                kv._write_checkpoint(active_split)
        return kv

    # ---------------------------------------------------------- 持久化辅助

    def _fsync_dir(self):
        descriptor = os.open(self._dir, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _atomic_write(self, name, payload):
        path = os.path.join(self._dir, name)
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, path)
        self._fsync_dir()

    def _persist_manifest(self, snapshot_name, records, shards):
        manifest = {
            "snapshot": snapshot_name,
            "records": [[m, b, _encode_key(s)] for m, b, s in records],
            "shards": [_encode_key(s) for s in shards],
        }
        self._atomic_write(_MANIFEST,
                           json.dumps(manifest, ensure_ascii=False, sort_keys=True))

    def _snapshot_payload(self, records, shards, data):
        items = []
        for shard in shards:
            bucket = data[shard]
            items.append({
                "shard": _encode_key(shard),
                "items": [[_encode_key(k), _encode_value(v)]
                          for k, v in bucket.items()],
            })
        return json.dumps({"data": items}, ensure_ascii=False, sort_keys=True)

    def _write_snapshot(self, name, records, shards):
        self._atomic_write(name, self._snapshot_payload(records, shards, self._data))

    def _wal_append(self, entry):
        if self._dir is None:
            return
        line = json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n"
        with self._wal_lock:
            if self._wal_fh is None:
                self._wal_fh = open(os.path.join(self._dir, _WAL),
                                    "a", encoding="utf-8")
            self._wal_fh.write(line)
            self._wal_fh.flush()
            os.fsync(self._wal_fh.fileno())

    def _wal_rotate(self):
        with self._wal_lock:
            if self._wal_fh is not None:
                self._wal_fh.close()
                self._wal_fh = None
            wal_path = os.path.join(self._dir, _WAL)
            if os.path.exists(wal_path):
                os.remove(wal_path)
        self._fsync_dir()

    def _checkpoint_payload(self, split):
        checkpoint = {
            "old": _encode_key(split.old),
            "target": _encode_key(split.new),
            "m": split._m,
            "b": split._b,
            "done": [_encode_key(k) for k in sorted(split.done, key=repr)],
        }
        return json.dumps(checkpoint, ensure_ascii=False, sort_keys=True)

    def _write_checkpoint(self, split):
        if self._dir is not None:
            self._atomic_write(_CHECKPOINT, self._checkpoint_payload(split))

    def _remove_checkpoint(self):
        if self._dir is not None:
            path = os.path.join(self._dir, _CHECKPOINT)
            if os.path.exists(path):
                os.remove(path)
                self._fsync_dir()

    # -------------------------------------------------------------- 路由

    def _owner_of_hash(self, h):
        for modulus, base, shard in self._records:
            if h % modulus == base:
                return shard, modulus, base
        raise AssertionError("unroutable hash")

    def shards(self):
        """返回全部已提交 shard id 的副本，改它不影响映射。"""
        return list(self._shards)

    def __len__(self):
        return len(self._shards)

    def shard_of(self, key):
        """返回 key 当前路由到的已提交 shard id；分裂中仍返回老片。"""
        shard, _, _ = self._owner_of_hash(_hash(key))
        return shard

    def active_split(self):
        """进行中的分裂句柄；没有分裂时返回 None。"""
        return self._split

    def close(self):
        """关掉底层 WAL 文件句柄；内存表本身仍可继续用。"""
        with self._wal_lock:
            if self._wal_fh is not None:
                self._wal_fh.close()
                self._wal_fh = None

    def begin_split(self, shard, new_shard=None):
        """给 shard 挂影子新片开始在线分裂，返回 SplitOperation。"""
        if self._split is not None:
            raise RuntimeError("another split is already active")
        if shard not in self._data:
            raise KeyError(shard)
        if new_shard is None:
            new_shard = "%s~half" % shard
        if new_shard in self._data or new_shard == shard:
            raise ValueError("duplicate shard id: %r" % (new_shard,))
        if new_shard is None or new_shard == "":
            raise ValueError("shard id must be non-empty")
        for modulus, base, owner in self._records:
            if owner == shard:
                break
        else:
            raise AssertionError("shard missing from routing table")

        split = SplitOperation(self, shard, new_shard, modulus, base)
        with self._commit_lock:
            if self._dir is not None:
                self._write_checkpoint(split)
            self._split = split
            self._locks[new_shard] = split.lock
        return split

    # -------------------------------------------------------------- WAL 回放

    def _replay_entry(self, entry, split):
        op = entry["op"]
        key = _decode_key(entry["k"])
        h = _hash(key)
        owner, modulus, base = self._owner_of_hash(h)
        if split is not None and owner == split.old:
            is_mover = h % (2 * modulus) == base + modulus
            if op == "put":
                value = _decode_value(entry["v"])
                self._data[split.old][key] = value
                if is_mover:
                    split.data[key] = value
            elif op == "del":
                self._data[split.old].pop(key, None)
                if is_mover:
                    split.data.pop(key, None)
            else:
                if key in self._data[split.old]:
                    split.data[key] = self._data[split.old].pop(key)
                    split.done.add(key)
        else:
            if op == "put":
                self._data[owner][key] = _decode_value(entry["v"])
            elif op == "del":
                self._data[owner].pop(key, None)

    # -------------------------------------------------------------- 读写

    def _route(self, key):
        h = _hash(key)
        owner, modulus, base = self._owner_of_hash(h)
        split = self._split
        if split is not None and owner == split.old:
            is_mover = h % (2 * split._m) == split._b + split._m
            return split, True, is_mover, key
        return None, False, False, key

    def put(self, key, value):
        """写入 key，返回当前路由认它的 shard id（分裂中为老片）。"""
        _encode_key(key)
        _encode_value(value)
        with self._commit_lock:
            split, in_domain, is_mover, _ = self._route(key)
            if split is None:
                owner = self.shard_of(key)
                self._wal_append({"op": "put", "k": _encode_key(key),
                                  "v": _encode_value(value)})
                with self._locks[owner]:
                    self._data[owner][key] = value
                return owner
            self._wal_append({"op": "put", "k": _encode_key(key),
                              "v": _encode_value(value)})
            with split.lock, self._locks[split.old]:
                self._data[split.old][key] = value
                if is_mover:
                    split.data[key] = value
            return split.old

    def get(self, key, default=None):
        """读 key：分裂中先问新片，没有再回老片捞；不存在返回 default。"""
        split, in_domain, _, _ = self._route(key)
        if split is None:
            owner = self.shard_of(key)
            with self._locks[owner]:
                return self._data[owner].get(key, default)
        with split.lock:
            if key in split.data:
                return split.data[key]
        with self._locks[split.old]:
            return self._data[split.old].get(key, default)

    def delete(self, key):
        """删除 key，删到了返回 True，本来就没有返回 False。"""
        with self._commit_lock:
            split, _, is_mover, _ = self._route(key)
            if split is None:
                owner = self.shard_of(key)
                self._wal_append({"op": "del", "k": _encode_key(key)})
                with self._locks[owner]:
                    if key in self._data[owner]:
                        del self._data[owner][key]
                        return True
                    return False
            self._wal_append({"op": "del", "k": _encode_key(key)})
            with split.lock, self._locks[split.old]:
                existed = key in self._data[split.old] or key in split.data
                self._data[split.old].pop(key, None)
                if is_mover:
                    split.data.pop(key, None)
                return existed

    def keys_in(self, shard):
        """返回某已提交片的全部 key（副本），顺序为写入顺序。"""
        if shard not in self._data:
            raise KeyError(shard)
        with self._locks[shard]:
            return list(self._data[shard])

    def size(self, shard):
        """某已提交片的键条数。"""
        if shard not in self._data:
            raise KeyError(shard)
        with self._locks[shard]:
            return len(self._data[shard])

    def distribution(self):
        """各已提交片条数 {shard: count}，空片计 0。"""
        return {s: self.size(s) for s in self._shards}

    def total(self):
        """全表键条数（分裂中按老片视图统计，迁移中的键不重复计）。"""
        split = self._split
        if split is None:
            return sum(self.size(s) for s in self._shards)
        total = 0
        for shard in self._shards:
            if shard != split.old:
                total += self.size(shard)
        with split.lock, self._locks[split.old]:
            old_data = self._data[split.old]
            total += len(old_data)
            total += sum(1 for key in split.data if key not in old_data)
        return total

    # ---------------------------------------------------------- 分裂状态机

    def _split_live(self, split):
        if self._split is not split or split.state != "migrating":
            raise RuntimeError("split is no longer active")

    def _snapshot_number(self):
        latest = 0
        if self._dir is not None:
            for name in os.listdir(self._dir):
                if name.startswith("snapshot.") and name.endswith(".json"):
                    try:
                        latest = max(latest, int(name[9:-5]))
                    except ValueError:
                        continue
        return latest + 1

    def _split_migrate(self, split, limit):
        self._split_live(split)
        moved = 0
        with split.lock, self._locks[split.old]:
            old_data = self._data[split.old]
            candidates = [key for key in old_data
                          if key not in split.done and split._mover_hash(_hash(key))]
            if limit is not None:
                candidates = candidates[:limit]
            if not candidates:
                # 收尾扫一遍：搬过的热点键可能又被双写弄脏了。
                candidates = [key for key in old_data
                              if split._mover_hash(_hash(key))]
                if limit is not None:
                    candidates = candidates[:limit]
            for key in candidates:
                self._wal_append({"op": "mv", "k": _encode_key(key)})
                split.data[key] = old_data.pop(key)
                split.done.add(key)
                moved += 1
        if moved:
            self._write_checkpoint(split)
        return moved

    def _split_progress(self, split):
        self._split_live(split)
        with split.lock, self._locks[split.old]:
            old_data = self._data[split.old]
            remaining = sum(1 for key in old_data
                            if split._mover_hash(_hash(key)))
            moved = sum(1 for key in split.data if key not in old_data)
        total = moved + remaining
        return {
            "old": split.old,
            "new": split.new,
            "moved": moved,
            "remaining": remaining,
            "total": total,
            "fraction": (moved / total) if total else 1.0,
        }

    def _next_records(self, split):
        records = []
        for modulus, base, owner in self._records:
            if owner == split.old:
                records.append((2 * modulus, base, split.old))
                records.append((2 * modulus, base + modulus, split.new))
            else:
                records.append((modulus, base, owner))
        records.sort(key=lambda item: (-item[0], item[1]))
        return records

    def _split_commit(self, split):
        self._split_live(split)
        with self._commit_lock:
            with split.lock, self._locks[split.old]:
                old_data = self._data[split.old]
                stragglers = [key for key in old_data
                              if split._mover_hash(_hash(key))]
                for key in stragglers:
                    self._wal_append({"op": "mv", "k": _encode_key(key)})
                    split.data[key] = old_data.pop(key)
                    split.done.add(key)
                if any(split._mover_hash(_hash(key)) for key in old_data):
                    raise RuntimeError("old shard still owns keys for the new shard")

                new_shards = self._shards + [split.new]
                new_records = self._next_records(split)
                if self._dir is not None:
                    new_data = dict(self._data)
                    new_data[split.new] = split.data
                    name = "snapshot.%d.json" % self._snapshot_number()
                    self._atomic_write(
                        name,
                        self._snapshot_payload(new_records, new_shards, new_data))
                    self._persist_manifest(name, new_records, new_shards)

                new_data = dict(self._data)
                new_data[split.new] = split.data
                self._data = new_data
                self._records = new_records
                self._shards = new_shards
                self._split = None
                split.state = "committed"
                split._kv = None

                if self._dir is not None:
                    current = name
                    self._wal_rotate()
                    self._remove_checkpoint()
                    for stale in os.listdir(self._dir):
                        if (stale.startswith("snapshot.") and stale.endswith(".json")
                                and stale != current):
                            os.remove(os.path.join(self._dir, stale))
                    self._fsync_dir()
        return split.new

    def _split_abort(self, split):
        self._split_live(split)
        with self._commit_lock:
            with split.lock, self._locks[split.old]:
                old_data = self._data[split.old]
                for key, value in split.data.items():
                    old_data[key] = value
                split.state = "aborting"

                if self._dir is not None:
                    self._wal_rotate()
                    name = "snapshot.%d.json" % self._snapshot_number()
                    self._write_snapshot(name, self._records, self._shards)
                    self._persist_manifest(name, self._records, self._shards)
                    self._remove_checkpoint()

                self._split = None
                del self._locks[split.new]
                split.state = "aborted"
                split.data = {}
                split.done.clear()
                split._kv = None
        return split.old
