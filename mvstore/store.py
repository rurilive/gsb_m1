"""单机 KV 存储，JSON 行 append 日志持久化，支持 MVCC 事务。

每次 put/delete 追加一条 JSON 记录，重启时按文件序重放恢复。
每个 key 维护一条版本链 (提交版本号, 值/墓碑)，全局版本号随每次
成功提交加一。begin() 开启的事务以 begin 时刻的全局版本号为快照，
commit 按写集做 first-committer-wins 冲突检测。
"""

import json
import os
import threading


_TOMBSTONE = object()


class ConflictError(Exception):
    """commit 时写集中的 key 在快照之后被别的提交改过，事务作废。"""


class Store:
    """单机 KV。

    path 为空时纯内存；给了 path 则所有写操作追加一份 JSON 行日志，
    重新打开同一 path 即恢复到最近状态。value 须可 JSON 序列化。

    begin() 开启 MVCC 事务：事务内 get 读 begin 时刻快照（写缓冲优先），
    put/delete 先落缓冲，commit 做 first-committer-wins 检测后生效，
    rollback 丢弃缓冲。非事务写相当于立即提交的单操作事务。
    """

    def __init__(self, path=None):
        self._lock = threading.Lock()
        self._versions = {}  # key -> [(version, value/_TOMBSTONE)]，按版本升序
        self._global_version = 0
        self._active = []  # 活跃事务的快照版本号
        self._path = path
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
                if rec["op"] == "put":
                    self._commit_locked({rec["key"]: rec["value"]})
                elif rec["op"] == "del":
                    self._commit_locked({rec["key"]: _TOMBSTONE})

    def _append(self, record):
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            f.write("\n")

    def _commit_locked(self, writes):
        """调用方须持有锁。写集整体以新版本号落版本链，返回新版本号。"""
        self._global_version += 1
        version = self._global_version
        for key, value in writes.items():
            self._versions.setdefault(key, []).append((version, value))
        return version

    def _latest_locked(self, key):
        versions = self._versions.get(key)
        if not versions:
            return None
        value = versions[-1][1]
        return None if value is _TOMBSTONE else value

    def _snapshot_get_locked(self, key, snapshot):
        versions = self._versions.get(key)
        if not versions:
            return None
        for version, value in reversed(versions):
            if version <= snapshot:
                return None if value is _TOMBSTONE else value
        return None

    def get(self, key):
        with self._lock:
            return self._latest_locked(key)

    def put(self, key, value):
        with self._lock:
            self._commit_locked({key: value})
        if self._path is not None:
            self._append({"op": "put", "key": key, "value": value})

    def delete(self, key):
        with self._lock:
            existed = self._latest_locked(key) is not None
            if existed:
                self._commit_locked({key: _TOMBSTONE})
        if existed and self._path is not None:
            self._append({"op": "del", "key": key})
        return existed

    def begin(self):
        """开启事务，快照为当前全局版本号。"""
        with self._lock:
            snapshot = self._global_version
            self._active.append(snapshot)
        return Transaction(self, snapshot)

    def _release_snapshot(self, snapshot):
        with self._lock:
            self._active.remove(snapshot)

    def gc(self):
        """回收活跃事务快照不再引用的旧版本。

        每个 key 保留最新版，外加每个活跃快照可见的最新一条版本；
        无活跃事务时每 key 只留最新版。
        """
        with self._lock:
            snapshots = list(self._active)
            for key, versions in self._versions.items():
                keep = [False] * len(versions)
                keep[-1] = True
                for snapshot in snapshots:
                    for i in range(len(versions) - 1, -1, -1):
                        if versions[i][0] <= snapshot:
                            keep[i] = True
                            break
                self._versions[key] = [e for i, e in enumerate(versions) if keep[i]]


class Transaction:
    """MVCC 事务。get 读快照（写缓冲优先），put/delete 落缓冲。"""

    def __init__(self, store, snapshot):
        self._store = store
        self._snapshot = snapshot
        self._writes = {}  # key -> value 或 _TOMBSTONE
        self._open = True

    def _check_open(self):
        if not self._open:
            raise RuntimeError("transaction already closed")

    def get(self, key):
        self._check_open()
        if key in self._writes:
            value = self._writes[key]
            return None if value is _TOMBSTONE else value
        with self._store._lock:
            return self._store._snapshot_get_locked(key, self._snapshot)

    def put(self, key, value):
        self._check_open()
        self._writes[key] = value

    def delete(self, key):
        self._check_open()
        existed = self.get(key) is not None
        self._writes[key] = _TOMBSTONE
        return existed

    def commit(self):
        """first-committer-wins：写集 key 快照后被提交过则抛 ConflictError。"""
        self._check_open()
        store = self._store
        try:
            with store._lock:
                for key in self._writes:
                    versions = store._versions.get(key)
                    if versions and versions[-1][0] > self._snapshot:
                        raise ConflictError(
                            "key %r modified after snapshot" % key)
                store._commit_locked(self._writes)
                if store._path is not None:
                    for key, value in self._writes.items():
                        if value is _TOMBSTONE:
                            store._append({"op": "del", "key": key})
                        else:
                            store._append(
                                {"op": "put", "key": key, "value": value})
        finally:
            self._close()

    def rollback(self):
        """丢弃写缓冲，释放快照。"""
        if self._open:
            self._writes.clear()
            self._close()

    def _close(self):
        self._open = False
        self._store._release_snapshot(self._snapshot)
