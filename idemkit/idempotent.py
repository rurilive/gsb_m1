"""幂等键层：同键 TTL 内重复提交直接返回首跑结果。

结果连同键与到期时间落 JSON 文件，进程重启后同键从文件重放。
过期条目惰性清理：不起后台线程，读写时顺手清。
"""

import hashlib
import json
import os
import threading
import time
from typing import Callable, Dict, Optional, Tuple

_MISSING = object()


class IdempotentSubmitter:
    """在 Dispatcher 外面套一层幂等键语义。

    submit(idem_key, task_name, payload)：同键在 TTL 内重复提交
    直接返回首跑结果，handler 不再执行；过期后重新执行并覆盖落盘。
    clock 可注入，默认 time.time，测试可拨快时钟验证过期重跑。
    """

    def __init__(
        self,
        dispatcher,
        store_dir: str,
        ttl: float,
        clock: Optional[Callable[[], float]] = None,
    ):
        self._dispatcher = dispatcher
        self._store_dir = store_dir
        self._ttl = ttl
        self._clock = clock or time.time
        self._mem: Dict[str, Tuple[float, object]] = {}
        self._locks: Dict[str, threading.Lock] = {}
        self._guard = threading.Lock()
        os.makedirs(store_dir, exist_ok=True)

    def submit(self, idem_key, task_name, payload):
        """同键 TTL 内返回首跑结果；并发同键只执行一次，其余等首跑结果。

        handler 抛出的异常原样上抛，且什么都不落盘，下次提交照常重试。
        """
        key = str(idem_key)
        cached = self._lookup(key)
        if cached is not _MISSING:
            return cached
        with self._lock_for(key):
            cached = self._lookup(key)  # 双查：等锁期间别的线程可能已跑完
            if cached is not _MISSING:
                return cached
            result = self._dispatcher.dispatch(task_name, payload)
            self._persist(key, result)
            return result

    def _lookup(self, key):
        self._cleanup()
        with self._guard:
            hit = self._mem.get(key)
        if hit is not None:
            expires_at, result = hit
            if self._clock() < expires_at:
                return result
            with self._guard:
                self._mem.pop(key, None)
        return self._load_file(key)

    def _load_file(self, key):
        path = self._path_for(key)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                record = json.load(fh)
        except (OSError, ValueError):
            return _MISSING
        if record.get("key") != key:
            return _MISSING
        expires_at = record["expires_at"]
        if self._clock() >= expires_at:
            self._remove(path)
            return _MISSING
        result = record["result"]
        with self._guard:
            self._mem[key] = (expires_at, result)
        return result

    def _persist(self, key, result):
        expires_at = self._clock() + self._ttl
        record = {"key": key, "expires_at": expires_at, "result": result}
        path = self._path_for(key)
        tmp = f"{path}.tmp.{os.getpid()}.{threading.get_ident()}"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(record, fh, ensure_ascii=False)
        os.replace(tmp, path)
        with self._guard:
            self._mem[key] = (expires_at, result)
        self._cleanup()

    def _cleanup(self):
        """惰性清理过期条目：读写时顺手扫一遍 store_dir。"""
        now = self._clock()
        try:
            names = os.listdir(self._store_dir)
        except OSError:
            return
        for name in names:
            if not name.endswith(".json"):
                continue
            path = os.path.join(self._store_dir, name)
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    record = json.load(fh)
            except (OSError, ValueError):
                continue
            expires_at = record.get("expires_at")
            if expires_at is not None and now >= expires_at:
                self._remove(path)
                key = record.get("key")
                if key is not None:
                    with self._guard:
                        self._mem.pop(key, None)

    def _path_for(self, key):
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return os.path.join(self._store_dir, f"{digest}.json")

    def _lock_for(self, key):
        with self._guard:
            lock = self._locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._locks[key] = lock
            return lock

    @staticmethod
    def _remove(path):
        try:
            os.remove(path)
        except OSError:
            pass
