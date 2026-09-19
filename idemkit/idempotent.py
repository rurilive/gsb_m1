"""幂等提交层：同键 TTL 内复用首跑结果，结果落盘可跨进程重放。

上游至少一次投递导致的重复提交，在这里被幂等键吸收：同键未过期
直接返回首跑结果，handler 不再执行。结果连同键与到期时间写入
store_dir 下的 JSON 文件（每键一文件，原子替换），进程重启后
同键从文件重放。过期条目在读写时惰性清理，不起后台线程。
"""

import hashlib
import json
import os
import threading
import time
from typing import Callable, Dict

_MISS = object()  # 缓存未命中哨兵，区别于合法的 None 结果


class IdempotentSubmitter:
    """在 Dispatcher 前加幂等键层。

    submit(idem_key, task_name, payload)：同键 TTL 内重复提交直接
    返回首跑结果；并发同键只执行一次，其余线程等首跑结果。
    clock 可注入（默认 time.time），便于测试拨快时钟验证过期。
    """

    def __init__(self, dispatcher, store_dir, ttl,
                 clock: Callable[[], float] = time.time):
        self._dispatcher = dispatcher
        self._store_dir = str(store_dir)
        self._ttl = float(ttl)
        self._clock = clock
        self._guard = threading.Lock()
        self._locks: Dict[str, threading.Lock] = {}
        os.makedirs(self._store_dir, exist_ok=True)

    def submit(self, idem_key: str, task_name: str, payload):
        """提交任务。同键未过期直接返回首跑结果，否则执行并落盘。"""
        self._sweep()
        cached = self._load(idem_key)
        if cached is not _MISS:
            return cached
        lock = self._lock_for(idem_key)
        with lock:
            # 双查：等锁期间可能已有同键线程跑完并落盘
            cached = self._load(idem_key)
            if cached is not _MISS:
                return cached
            result = self._dispatcher.dispatch(task_name, payload)
            self._persist(idem_key, result)
            return result

    def _path(self, idem_key: str) -> str:
        digest = hashlib.sha256(idem_key.encode("utf-8")).hexdigest()
        return os.path.join(self._store_dir, f"{digest}.json")

    def _lock_for(self, idem_key: str) -> threading.Lock:
        with self._guard:
            return self._locks.setdefault(idem_key, threading.Lock())

    def _load(self, idem_key: str):
        try:
            with open(self._path(idem_key), "r", encoding="utf-8") as fh:
                entry = json.load(fh)
        except (OSError, ValueError):
            return _MISS
        if entry.get("expires_at", 0) <= self._clock():
            self._remove(idem_key)  # 读到过期条目，顺手清掉
            return _MISS
        return entry["result"]

    def _persist(self, idem_key: str, result) -> None:
        entry = {
            "key": idem_key,
            "expires_at": self._clock() + self._ttl,
            "result": result,
        }
        tmp = self._path(idem_key) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(entry, fh, ensure_ascii=False)
        os.replace(tmp, self._path(idem_key))

    def _remove(self, idem_key: str) -> None:
        try:
            os.unlink(self._path(idem_key))
        except OSError:
            pass

    def _sweep(self) -> None:
        """惰性清理：提交时顺手删掉 store_dir 里的过期条目。"""
        now = self._clock()
        for name in os.listdir(self._store_dir):
            if not name.endswith(".json"):
                continue
            path = os.path.join(self._store_dir, name)
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    entry = json.load(fh)
            except (OSError, ValueError):
                continue
            if entry.get("expires_at", 0) <= now:
                try:
                    os.unlink(path)
                except OSError:
                    pass
