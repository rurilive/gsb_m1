"""幂等键存储：按幂等键记住已处理请求的结果。

上游提交前先用幂等键问一遍要不要干活，干完把结果记回键上；同一个键再
提交时直接把上次的结果回放出去，避免重复扣款。时间读取统一走注入的
clock；记录可以落一份到磁盘，进程重启后接着用。纯标准库实现。
"""

import json
import os
import tempfile
import threading
import time


class TruncatedResult:
    """结果体积超上限时落下的截断标记。

    真正的结果没有进缓存，取回时拿到的是这个标记对象；truncated 恒为
    True，调用方据此知道这条结果被截断过、不能当正常回执回放。
    """

    __slots__ = ("original_size", "max_size")

    def __init__(self, original_size, max_size):
        self.original_size = original_size
        self.max_size = max_size

    @property
    def truncated(self):
        return True

    def __repr__(self):
        return (
            "TruncatedResult(original_size=%r, max_size=%r)"
            % (self.original_size, self.max_size)
        )

    def __eq__(self, other):
        return (
            isinstance(other, TruncatedResult)
            and self.original_size == other.original_size
            and self.max_size == other.max_size
        )


class _Record:
    """一条幂等记录。

    result 为 None 表示键已经占上但结果还没写回来；finished_at 为 None
    表示这次处理还没收尾。
    """

    __slots__ = ("result", "created_at", "finished_at")

    def __init__(self, result, created_at, finished_at):
        self.result = result
        self.created_at = created_at
        self.finished_at = finished_at


class IdempotencyStore:
    """按幂等键记住请求结果的存储。

    ttl: 记录存活秒数，从请求完成时刻起算；None 表示永不过期。
    clock: 返回当前时刻的可调用对象，默认 time.monotonic，测试可注入。
    path: 落盘文件路径；None 表示只放在内存里。
    max_result_size: 单个结果允许占用的最大字节数（按 JSON 序列化后的
        UTF-8 字节计）；None 表示不限。超限的结果不会进缓存，替换成
        TruncatedResult 截断标记。
    """

    def __init__(self, ttl=None, clock=time.monotonic, path=None,
                 max_result_size=None):
        if ttl is not None and ttl <= 0:
            raise ValueError("ttl must be positive")
        if max_result_size is not None and max_result_size <= 0:
            raise ValueError("max_result_size must be positive")
        self._ttl = ttl
        self._clock = clock
        self._path = path
        self._max_result_size = max_result_size
        self._lock = threading.Lock()
        self._records = {}
        if path is not None:
            self._load()

    # -- 对外接口 --

    def begin(self, key):
        """提交前问一句这个键要不要干活。

        返回 True 表示该由本次请求处理；返回 False 表示这个键已经处理过，
        调用方应当改用 get(key) 取回上次的结果。
        """
        key = self._normalize(key)
        now = self._clock()
        with self._lock:
            self._purge(now)
            record = self._records.get(key)
            if record is not None:
                return False
            # 先把键占上，免得同一个键并发送进来跑两遍
            self._records[key] = _Record(None, now, None)
            self._save()
            return True

    def finish(self, key, result):
        """把处理结果记到键上，这个键之后就算已处理。"""
        key = self._normalize(key)
        now = self._clock()
        with self._lock:
            result = self._cap_result(result)
            record = self._records.get(key)
            if record is None:
                self._records[key] = _Record(result, now, now)
            else:
                record.result = result
                record.finished_at = now
            self._save()
            return result

    def get(self, key):
        """取这个键已经记下的结果，没有就返回 None。"""
        key = self._normalize(key)
        now = self._clock()
        with self._lock:
            self._purge(now)
            record = self._records.get(key)
            if record is None:
                return None
            return record.result

    def release(self, key):
        """释放一个还没收尾的占位（比如处理中途失败后）。

        释放后同一个键可以重新 begin；已经收尾、记下结果的键不受影响，
        返回 False。这样下游超时不会把键永久卡死。
        """
        key = self._normalize(key)
        with self._lock:
            record = self._records.get(key)
            if record is None or record.finished_at is not None:
                return False
            del self._records[key]
            self._save()
            return True

    def renew(self, key):
        """给还在处理中的键续期，长流程可以中途延长占位的存活时间。

        把占位的存活计时点推到当前时刻，避免单子还在跑就按开工时刻
        过期；键不存在或已经收尾时返回 False。
        """
        key = self._normalize(key)
        now = self._clock()
        with self._lock:
            record = self._records.get(key)
            if record is None:
                return False
            record.created_at = now
            if record.finished_at is not None:
                record.finished_at = now
            self._save()
            return True

    # -- 内部实现 --

    def _normalize(self, key):
        """键的规范化：只去掉首尾空白。

        大小写是单号的一部分，不能折叠，否则只差大小写的两笔单会被
        当成同一笔、回放错回执。
        """
        return key.strip()

    def _purge(self, now):
        """清掉已经过期的记录。"""
        if self._ttl is None:
            return
        expired = [key for key, record in self._records.items()
                   if self._is_expired(record, now)]
        for key in expired:
            del self._records[key]

    def _is_expired(self, record, now):
        """一条记录此刻是否过期。

        有效期从完成时刻起算，耗时再长的单子只要还在 ttl 内收工，结果
        就完整存活一个 ttl；还没收尾的占位仍从占键时刻起算，防止崩溃
        残留的占位把键永久占死。
        """
        anchor = record.finished_at
        if anchor is None:
            anchor = record.created_at
        return now - anchor >= self._ttl

    def _cap_result(self, result):
        """结果超体积上限时换成截断标记，不把缓存撑爆。"""
        if self._max_result_size is None:
            return result
        size = len(json.dumps(result, ensure_ascii=False).encode("utf-8"))
        if size <= self._max_result_size:
            return result
        return TruncatedResult(size, self._max_result_size)

    def _load(self):
        """从磁盘读回上次的记录。"""
        if not os.path.exists(self._path):
            return
        with open(self._path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        for key, item in raw.items():
            result = item["result"]
            if isinstance(result, dict) and result.get("__truncated__"):
                result = TruncatedResult(
                    result["original_size"], result["max_size"]
                )
            self._records[key] = _Record(
                result, item["created_at"], item["finished_at"]
            )

    def _save(self):
        """把当前记录写到磁盘。"""
        if self._path is None:
            return
        raw = {
            key: {
                "result": self._dump_result(record.result),
                "created_at": record.created_at,
                "finished_at": record.finished_at,
            }
            for key, record in self._records.items()
        }
        directory = os.path.dirname(self._path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=directory or ".", prefix=".idemkey-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(raw, fh)
            os.replace(tmp_name, self._path)
        except BaseException:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
            raise

    @staticmethod
    def _dump_result(result):
        """截断标记落盘时带上类型标签，读回时还原。"""
        if isinstance(result, TruncatedResult):
            return {
                "__truncated__": True,
                "original_size": result.original_size,
                "max_size": result.max_size,
            }
        return result
