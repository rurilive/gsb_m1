"""幂等提交层：同键 TTL 内只真实执行一次。

在 Dispatcher 之上包一层。同一个 idem_key 在 TTL 窗口内的重复
提交直接返回首跑结果，handler 不再执行；结果连同键与到期时间落
JSON 文件，进程重启后新实例指向同一目录即可重放。

并发同键只执行一次：线程锁加双查，其余线程等首跑结果。
过期条目惰性清理，不起后台线程，读写时顺手清。
"""

import hashlib
import json
import os
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, Optional

from idemkit.dispatcher import Dispatcher


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value)


class IdempotentSubmitter:
    """按 idem_key 去重的同步提交器。"""

    def __init__(
        self,
        dispatcher: Dispatcher,
        store_dir: str,
        ttl: float,
        clock: Callable[[], datetime] = _utcnow,
    ):
        self._dispatcher = dispatcher
        self._store_dir = store_dir
        self._ttl = ttl
        self._clock = clock
        os.makedirs(self._store_dir, exist_ok=True)
        self._locks_guard = threading.Lock()
        self._locks: Dict[str, threading.Lock] = {}

    def submit(self, idem_key: str, task_name: str, payload):
        """同键 TTL 内重复提交直接返回首跑结果，否则执行一次并落盘。"""
        now = self._clock()
        self._sweep(now)
        lock = self._lock_for(idem_key)
        with lock:
            record = self._load_record(idem_key, now)
            if record is not None:
                return record["result"]
            result = self._dispatcher.dispatch(task_name, payload)
            self._write_record(idem_key, task_name, result, now)
            return result

    def _lock_for(self, idem_key: str) -> threading.Lock:
        with self._locks_guard:
            lock = self._locks.get(idem_key)
            if lock is None:
                lock = threading.Lock()
                self._locks[idem_key] = lock
            return lock

    def _path_for(self, idem_key: str) -> str:
        digest = hashlib.sha256(idem_key.encode("utf-8")).hexdigest()
        return os.path.join(self._store_dir, f"idem-{digest}.json")

    def _load_record(self, idem_key: str, now: datetime) -> Optional[dict]:
        path = self._path_for(idem_key)
        try:
            with open(path, "r", encoding="utf-8") as f:
                record = json.load(f)
        except FileNotFoundError:
            return None
        except (ValueError, OSError):
            return None
        if record.get("idem_key") != idem_key:
            return None
        if _parse(record["expires_at"]) <= now:
            self._remove(path)
            return None
        return record

    def _write_record(self, idem_key, task_name, result, now: datetime) -> None:
        record = {
            "idem_key": idem_key,
            "task_name": task_name,
            "result": result,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=self._ttl)).isoformat(),
        }
        path = self._path_for(idem_key)
        fd, tmp = tempfile.mkstemp(dir=self._store_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(record, f, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        except BaseException:
            self._remove(tmp)
            raise

    def _sweep(self, now: datetime) -> None:
        try:
            names = os.listdir(self._store_dir)
        except FileNotFoundError:
            return
        for name in names:
            if not name.startswith("idem-") or not name.endswith(".json"):
                continue
            path = os.path.join(self._store_dir, name)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    record = json.load(f)
                if _parse(record["expires_at"]) <= now:
                    self._remove(path)
            except (FileNotFoundError, ValueError, OSError, KeyError):
                continue

    @staticmethod
    def _remove(path: str) -> None:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
