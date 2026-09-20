"""幂等提交层：同键 TTL 内复用首跑结果，结果落盘可跨进程重放。

上游是至少一次投递，同一个任务可能被重复提交。本层在 Dispatcher
外面加幂等键：同键在 TTL 内只真正执行一次，重复提交直接返回首跑
结果；结果连同键与到期时间写入 store_dir 下的 JSON 文件，进程
重启后新实例从文件重放。过期条目在读写时惰性清理，不起后台线程。
"""

import hashlib
import json
import os
import threading
import time
from pathlib import Path

_MISSING = object()


class IdempotentSubmitter:
    """在 Dispatcher 外套一层幂等键。

    submit(idem_key, task_name, payload)：同键 TTL 内的重复提交
    直接返回首跑结果，handler 不再执行；并发同键只执行一次，
    其余线程等首跑结果。clock 可注入（默认 time.time），便于
    测试拨快时钟验证过期重跑。
    """

    def __init__(self, dispatcher, store_dir, ttl, clock=None):
        self._dispatcher = dispatcher
        self._store_dir = Path(store_dir)
        self._ttl = ttl
        self._clock = clock or time.time
        self._cache = {}
        self._locks = {}
        self._guard = threading.Lock()
        self._store_dir.mkdir(parents=True, exist_ok=True)

    def submit(self, idem_key, task_name, payload):
        """提交任务。同键未过期则返回首跑结果，否则执行并落盘。"""
        now = self._clock()
        self._purge_expired(now)
        hit = self._lookup(idem_key, now)
        if hit is not _MISSING:
            return hit
        lock = self._lock_for(idem_key)
        with lock:
            now = self._clock()
            hit = self._lookup(idem_key, now)
            if hit is not _MISSING:
                return hit
            result = self._dispatcher.dispatch(task_name, payload)
            self._store(idem_key, task_name, result, now + self._ttl)
            return result

    def _lock_for(self, idem_key):
        with self._guard:
            return self._locks.setdefault(idem_key, threading.Lock())

    def _path_for(self, idem_key):
        digest = hashlib.sha256(idem_key.encode("utf-8")).hexdigest()
        return self._store_dir / f"{digest}.json"

    def _lookup(self, idem_key, now):
        entry = self._cache.get(idem_key)
        if entry is None:
            entry = self._read_file(idem_key)
            if entry is not None:
                self._cache[idem_key] = entry
        if entry is None:
            return _MISSING
        if entry["expires_at"] <= now:
            self._evict(idem_key)
            return _MISSING
        return entry["result"]

    def _read_file(self, idem_key):
        path = self._path_for(idem_key)
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(entry, dict) or entry.get("key") != idem_key:
            return None
        return entry

    def _store(self, idem_key, task_name, result, expires_at):
        entry = {
            "key": idem_key,
            "task_name": task_name,
            "result": result,
            "expires_at": expires_at,
        }
        path = self._path_for(idem_key)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(entry, ensure_ascii=False), encoding="utf-8"
        )
        os.replace(tmp, path)
        self._cache[idem_key] = entry

    def _evict(self, idem_key):
        self._cache.pop(idem_key, None)
        try:
            self._path_for(idem_key).unlink()
        except OSError:
            pass

    def _purge_expired(self, now):
        for key, entry in list(self._cache.items()):
            if entry["expires_at"] <= now:
                self._cache.pop(key, None)
        for path in self._store_dir.glob("*.json"):
            try:
                entry = json.loads(path.read_text(encoding="utf-8"))
                expired = entry["expires_at"] <= now
            except (OSError, ValueError, KeyError, TypeError):
                expired = True
            if expired:
                try:
                    path.unlink()
                except OSError:
                    pass
