"""幂等提交层：同键 TTL 内复用首跑结果，结果落盘可重放。

上游是至少一次投递，同一任务可能被重复提交。本层在 Dispatcher
外面包一层幂等键语义：同键在 TTL 内只真实执行一次，重复提交
直接返回首跑结果；结果连同键与到期时间写入 store_dir 下的
JSON 文件，进程重启后新实例指向同一目录即可重放。
"""

import hashlib
import json
import os
import threading
import time


class IdempotentSubmitter:
    """幂等提交入口：submit(idem_key, task_name, payload)。

    - 同键 TTL 内重复提交直接返回首跑结果，handler 不再执行
    - 结果落盘为 JSON 文件，重启后同键从文件重放
    - 并发同键只执行一次：每键一把锁加双查，其余线程等首跑结果
    - 过期条目在读写时惰性清理，无后台线程
    - clock 可注入（默认 time.time），测试可拨快时钟验证过期重跑
    """

    def __init__(self, dispatcher, store_dir, ttl, clock=time.time):
        self._dispatcher = dispatcher
        self._store_dir = str(store_dir)
        self._ttl = ttl
        self._clock = clock
        self._guard = threading.Lock()
        self._locks = {}
        os.makedirs(self._store_dir, exist_ok=True)

    def submit(self, idem_key, task_name, payload):
        """提交任务。同键未过期则返回首跑结果，否则执行并落盘。"""
        self._purge_expired()
        path = self._path_for(idem_key)
        entry = self._read_fresh(path)
        if entry is not None:
            return entry["result"]
        lock = self._lock_for(idem_key)
        with lock:
            # 双查：等锁期间首跑可能已完成并落盘
            entry = self._read_fresh(path)
            if entry is not None:
                return entry["result"]
            result = self._dispatcher.dispatch(task_name, payload)
            self._write_entry(path, idem_key, task_name, result)
            return result

    def _path_for(self, idem_key):
        digest = hashlib.sha256(str(idem_key).encode("utf-8")).hexdigest()
        return os.path.join(self._store_dir, f"{digest}.json")

    def _lock_for(self, idem_key):
        with self._guard:
            return self._locks.setdefault(idem_key, threading.Lock())

    def _read_fresh(self, path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                entry = json.load(fh)
        except (OSError, ValueError):
            return None
        if self._clock() >= entry["expires_at"]:
            self._remove(path)
            return None
        return entry

    def _write_entry(self, path, idem_key, task_name, result):
        entry = {
            "key": idem_key,
            "task_name": task_name,
            "result": result,
            "expires_at": self._clock() + self._ttl,
        }
        tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(entry, fh, ensure_ascii=False)
        os.replace(tmp, path)

    def _purge_expired(self):
        now = self._clock()
        for name in os.listdir(self._store_dir):
            if not name.endswith(".json"):
                continue
            path = os.path.join(self._store_dir, name)
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    expires_at = json.load(fh)["expires_at"]
            except (OSError, ValueError, KeyError):
                self._remove(path)
                continue
            if now >= expires_at:
                self._remove(path)

    @staticmethod
    def _remove(path):
        try:
            os.remove(path)
        except OSError:
            pass
