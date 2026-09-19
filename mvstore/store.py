"""单机 KV 存储，JSON 行 append 日志持久化，带 MVCC 事务。

每次 put/delete 追加一条 JSON 记录，重启时按文件序重放恢复。
事务（begin/commit/rollback）提供 begin 时刻快照隔离，提交按写集做
first-committer-wins 冲突检测，成功提交推进全局版本号。
"""

import json
import os
import threading


class ConflictError(Exception):
    """事务提交时发现写集 key 自快照以来已被他人提交，事务作废。"""


_TOMBSTONE = object()


def _visible_index(versions, snapshot):
    """versions 按版本号升序排列，返回 <= snapshot 的最后一个下标，没有则 -1。"""
    lo, hi = 0, len(versions)
    while lo < hi:
        mid = (lo + hi) // 2
        if versions[mid][0] <= snapshot:
            lo = mid + 1
        else:
            hi = mid
    return lo - 1


class Store:
    """单机 KV。

    path 为空时纯内存；给了 path 则所有写操作追加一份 JSON 行日志，
    重新打开同一 path 即恢复到最近状态。value 须可 JSON 序列化。

    MVCC 形态：
    - _versions[key] = [(version, value|_TOMBSTONE)]，_TOMBSTONE 为删除标记
    - _key_ver[key] 记录该 key 最后一次被提交的版本号
    - _version 为全局版本号，每次成功提交（含事务与单操作）加一
    - _active 记录所有活跃事务的快照版本，供 gc 确定安全水位
    - value 为 _TOMBSTONE 哨兵表示该版本是一次删除
    """

    def __init__(self, path=None):
        self._lock = threading.Lock()
        self._versions = {}
        self._key_ver = {}
        self._version = 0
        self._active = {}
        self._path = path
        self._tx_seq = 0
        if path is not None:
            self._replay()

    def _replay(self):
        if not os.path.exists(self._path):
            return
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                ver = rec.get("ver")
                if rec["op"] == "put":
                    if ver is None:
                        # 旧格式日志：按文件序补版本号
                        self._version += 1
                        ver = self._version
                    self._commit_write(rec["key"], rec["value"], ver)
                elif rec["op"] == "del":
                    if ver is None:
                        self._version += 1
                        ver = self._version
                    self._commit_write(rec["key"], _TOMBSTONE, ver)

    def _commit_write(self, key, value, ver):
        """把一个版本写入内存结构并登记 key 最后提交版本（调用方持锁）。"""
        self._versions.setdefault(key, []).append((ver, value))
        self._key_ver[key] = ver
        if ver > self._version:
            self._version = ver

    def _append(self, record):
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            f.write("\n")

    def _read(self, key, snapshot):
        """读 key 在 snapshot 时刻可见的值，不存在或已删除返回 None。"""
        versions = self._versions.get(key)
        if not versions:
            return None
        idx = _visible_index(versions, snapshot)
        if idx < 0:
            return None
        value = versions[idx][1]
        return None if value is _TOMBSTONE else value

    def _present(self, key, snapshot):
        """key 在 snapshot 时刻是否存在（值为 None 也算存在，删除不算）。"""
        versions = self._versions.get(key)
        if not versions:
            return False
        idx = _visible_index(versions, snapshot)
        return idx >= 0 and versions[idx][1] is not _TOMBSTONE

    def begin(self):
        """开启事务，事务内 get 读 begin 时刻的快照。"""
        with self._lock:
            self._tx_seq += 1
            tx_id = self._tx_seq
            tx = Transaction(self, tx_id, self._version)
            self._active[tx_id] = tx
        return tx

    def gc(self):
        """回收任何活跃事务快照都不再引用的旧版本。

        保留：每个活跃事务快照在该 key 上可见的版本，以及全局最新版
        （新事务从当前版本开快照）。无活跃事务时即每 key 只留最新版；
        最新版是删除标记且无快照需要时，整个 key 一并清掉。
        """
        with self._lock:
            snapshots = sorted({tx.snapshot for tx in self._active.values()})
            for key in list(self._versions):
                versions = self._versions[key]
                keep = {len(versions) - 1}
                for snapshot in snapshots:
                    idx = _visible_index(versions, snapshot)
                    if idx >= 0:
                        keep.add(idx)
                retained = [versions[i] for i in sorted(keep)]
                if len(retained) == 1 and retained[0][1] is _TOMBSTONE:
                    del self._versions[key]
                else:
                    self._versions[key] = retained

    def get(self, key):
        with self._lock:
            return self._read(key, self._version)

    def put(self, key, value):
        """单操作即一次自动提交：成功即推进版本。"""
        with self._lock:
            self._version += 1
            ver = self._version
            self._commit_write(key, value, ver)
            if self._path is not None:
                self._append({"op": "put", "key": key, "value": value, "ver": ver})

    def delete(self, key):
        """单操作即一次自动提交，返回是否真的删了。"""
        with self._lock:
            existed = self._present(key, self._version)
            self._version += 1
            ver = self._version
            self._commit_write(key, _TOMBSTONE, ver)
            if existed and self._path is not None:
                self._append({"op": "del", "key": key, "ver": ver})
        return existed


class Transaction:
    """MVCC 事务：快照读 + 缓冲写，提交时 first-committer-wins 检测。"""

    def __init__(self, store, tx_id, snapshot):
        self._store = store
        self._tx_id = tx_id
        self.snapshot = snapshot
        self._buffer = {}
        self._active = True

    def _check_active(self):
        if not self._active:
            raise RuntimeError("事务已结束（提交或回滚），不能再使用")

    def get(self, key):
        self._check_active()
        if key in self._buffer:
            value = self._buffer[key]
            return None if value is _TOMBSTONE else value
        with self._store._lock:
            return self._store._read(key, self.snapshot)

    def put(self, key, value):
        self._check_active()
        self._buffer[key] = value

    def delete(self, key):
        self._check_active()
        self._buffer[key] = _TOMBSTONE

    def commit(self):
        """first-committer-wins：写集 key 快照后被他人提交过则冲突作废。"""
        self._check_active()
        store = self._store
        with store._lock:
            for key in self._buffer:
                if store._key_ver.get(key, 0) > self.snapshot:
                    self._active = False
                    store._active.pop(self._tx_id, None)
                    raise ConflictError(
                        "key %r 在快照（版本 %d）之后已被他人提交" % (key, self.snapshot)
                    )
            store._version += 1
            ver = store._version
            records = []
            for key, value in self._buffer.items():
                store._commit_write(
                    key, _TOMBSTONE if value is _TOMBSTONE else value, ver
                )
                if value is _TOMBSTONE:
                    records.append({"op": "del", "key": key, "ver": ver})
                else:
                    records.append(
                        {"op": "put", "key": key, "value": value, "ver": ver}
                    )
            if store._path is not None:
                for rec in records:
                    store._append(rec)
            self._active = False
            store._active.pop(self._tx_id, None)
        return ver

    def rollback(self):
        """丢弃写缓冲，事务结束。"""
        self._check_active()
        self._active = False
        self._buffer = {}
        with self._store._lock:
            self._store._active.pop(self._tx_id, None)
