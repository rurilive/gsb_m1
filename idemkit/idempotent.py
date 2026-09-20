"""幂等提交层：同键 TTL 内只执行一次，结果落 JSON 可跨进程重放。

上游是至少一次投递，同一任务可能被重复提交。IdempotentSubmitter
以 idem_key 去重：

- 同键在 TTL 内重复提交，直接返回首跑结果，handler 不再执行
- 结果连同键与到期时间落 JSON 文件，进程重启后同键从文件重放
- 同进程并发同键：每键一把锁 + 双查，只有一个线程执行，
  其余线程等待首跑结果
- 过期条目惰性清理：不起后台线程，只在读写时顺手清理
- clock 可注入，便于测试拨快时钟验证过期重跑
"""

import hashlib
import json
import os
import tempfile
import threading
import time


class IdempotentSubmitter:
    """给 Dispatcher 加一层幂等键。"""

    def __init__(self, dispatcher, store_dir, ttl, clock=time.monotonic):
        self._dispatcher = dispatcher
        self._store_dir = store_dir
        self._ttl = ttl
        self._clock = clock
        self._key_locks = {}
        self._key_locks_guard = threading.Lock()
        os.makedirs(self._store_dir, exist_ok=True)

    def submit(self, idem_key, task_name, payload):
        """按 idem_key 幂等提交。同键 TTL 内重复提交返回首跑结果。"""
        # 顺手清一次过期条目（读路径惰性清理）
        self._purge_expired()

        # 无锁快路径：已有未过期记录直接重放
        record = self._load_record(idem_key)
        if record is not None:
            return record["result"]

        lock = self._get_key_lock(idem_key)
        with lock:
            # 双查：拿到锁期间别的线程可能已经执行并落盘
            record = self._load_record(idem_key)
            if record is not None:
                return record["result"]

            # 首跑：dispatch 抛异常时不落盘，后续提交按至少一次语义重跑
            result = self._dispatcher.dispatch(task_name, payload)
            self._store_record(idem_key, result)
            return result

    def _get_key_lock(self, idem_key):
        with self._key_locks_guard:
            lock = self._key_locks.get(idem_key)
            if lock is None:
                lock = threading.Lock()
                self._key_locks[idem_key] = lock
            return lock

    def _path_for(self, idem_key):
        digest = hashlib.sha256(idem_key.encode("utf-8")).hexdigest()
        return os.path.join(self._store_dir, digest + ".json")

    def _load_record(self, idem_key):
        path = self._path_for(idem_key)
        try:
            with open(path, "r", encoding="utf-8") as f:
                record = json.load(f)
        except FileNotFoundError:
            return None
        except (ValueError, OSError):
            # 损坏或无法读取的文件无法重放，交给锁内重新执行
            return None
        if record.get("expires_at", 0) <= self._clock():
            try:
                os.remove(path)
            except OSError:
                pass
            return None
        return record

    def _store_record(self, idem_key, result):
        record = {
            "idem_key": idem_key,
            "result": result,
            "expires_at": self._clock() + self._ttl,
        }
        path = self._path_for(idem_key)
        fd, tmp_path = tempfile.mkstemp(dir=self._store_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(record, f, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
        except BaseException:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise
        # 写完顺手清一次过期条目（写路径惰性清理）
        self._purge_expired()

    def _purge_expired(self):
        now = self._clock()
        try:
            names = os.listdir(self._store_dir)
        except FileNotFoundError:
            return
        for name in names:
            if not name.endswith(".json"):
                continue
            path = os.path.join(self._store_dir, name)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    record = json.load(f)
            except (FileNotFoundError, ValueError, OSError):
                continue
            if record.get("expires_at", 0) <= now:
                try:
                    os.remove(path)
                except OSError:
                    pass
