"""幂等键存储：按幂等键记住已处理请求的结果。

上游提交前先用幂等键问一遍要不要干活，干完把结果记回键上；同一个键再
提交时直接把上次的结果回放出去，避免重复扣款。时间读取统一走注入的
clock；记录可以落一份到磁盘，进程重启后接着用。纯标准库实现。
"""

import json
import os
import threading
import time


class TruncatedResult:
    """结果体积超过上限时留下的截断标记。

    原始结果不会落库，取回时拿到本对象即可判断这笔的结果被截断过：
    ``size`` 是原始结果的字节数，``limit`` 是配置的上限。
    """

    __slots__ = ("size", "limit")

    def __init__(self, size, limit):
        self.size = size
        self.limit = limit

    def __repr__(self):
        return "TruncatedResult(size={}, limit={})".format(self.size, self.limit)

    def __eq__(self, other):
        if not isinstance(other, TruncatedResult):
            return NotImplemented
        return self.size == other.size and self.limit == other.limit

    def __hash__(self):
        return hash((TruncatedResult, self.size, self.limit))


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

    ttl: 记录存活秒数，从请求完成（finish）时刻起算；None 表示永不过期。
        因此处理耗时不计入有效期，长流程相当于在收工时续期一次。
    clock: 返回当前时刻的可调用对象，默认 time.monotonic，测试可注入。
    path: 落盘文件路径；None 表示只放在内存里。
    max_result_size: 结果体积上限（JSON 序列化后的 UTF-8 字节数）；None
        表示不限制。超限时只保存一个 TruncatedResult 截断标记，取回时可
        据此判断结果被截断过，避免大结果撑爆缓存/落盘文件。
    """

    def __init__(self, ttl=None, clock=time.monotonic, path=None,
                 max_result_size=None):
        if ttl is not None and ttl <= 0:
            raise ValueError("ttl must be positive")
        if max_result_size is not None and (
            not isinstance(max_result_size, int)
            or isinstance(max_result_size, bool)
            or max_result_size <= 0
        ):
            raise ValueError("max_result_size must be a positive integer")
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

        只占了键却一直没有 finish 的记录（处理中途失败、进程崩溃留下的
        残键）不挡重入：本次可以重新开工，避免键被永久卡死、重发只拿到
        空结果。
        """
        key = self._normalize(key)
        now = self._clock()
        with self._lock:
            self._purge(now)
            record = self._records.get(key)
            if record is not None and record.finished_at is not None:
                return False
            # 没有记录，或是上一次处理没写完结果的残键：本次重新占键开工
            self._records[key] = _Record(None, now, None)
            self._save()
            return True

    def finish(self, key, result):
        """把处理结果记到键上，这个键之后就算已处理。

        返回实际存下的结果；若体积超限，返回的是 TruncatedResult 标记。
        """
        key = self._normalize(key)
        now = self._clock()
        with self._lock:
            record = self._records.get(key)
            if record is None:
                record = _Record(None, now, None)
                self._records[key] = record
            stored = self._truncate_if_needed(result)
            record.result = stored
            record.finished_at = now
            self._save()
            return stored

    def get(self, key):
        """取这个键已经记下的结果，没有（或还没写完）就返回 None。"""
        key = self._normalize(key)
        now = self._clock()
        with self._lock:
            self._purge(now)
            record = self._records.get(key)
            if record is None or record.finished_at is None:
                return None
            return record.result

    # -- 内部实现 --

    def _normalize(self, key):
        """键的规范化：只去掉首尾空白，保留原大小写。

        大小写不同的单号就是两笔不同的单，绝不能并成一笔。
        """
        return key.strip()

    def _purge(self, now):
        """清掉已经过期的记录。"""
        if self._ttl is None:
            return
        expired = []
        for key, record in self._records.items():
            # 有效期从完成时刻起算；还没收尾的在途键不参与过期清理，
            # 否则长流程会在收工瞬间被判过期。
            if record.finished_at is None:
                continue
            if now - record.finished_at >= self._ttl:
                expired.append(key)
        if not expired:
            return
        for key in expired:
            del self._records[key]
        self._save()

    def _truncate_if_needed(self, result):
        """结果超体积上限时换成截断标记。"""
        if self._max_result_size is None or isinstance(result, TruncatedResult):
            return result
        size = len(self._dumps(result))
        if size <= self._max_result_size:
            return result
        return TruncatedResult(size=size, limit=self._max_result_size)

    @staticmethod
    def _dumps(result):
        return json.dumps(result, ensure_ascii=False).encode("utf-8")

    def _load(self):
        """从磁盘读回上次的记录。"""
        if not os.path.exists(self._path):
            return
        with open(self._path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        for key, item in raw.items():
            result = item["result"]
            if (
                isinstance(result, dict)
                and result.get(_TRUNCATED_MARKER_KEY) is True
            ):
                result = TruncatedResult(result["size"], result["limit"])
            self._records[key] = _Record(
                result, item["created_at"], item["finished_at"]
            )

    def _save(self):
        """把当前记录写到磁盘。"""
        if self._path is None:
            return
        raw = {
            key: {
                "result": self._encode(record.result),
                "created_at": record.created_at,
                "finished_at": record.finished_at,
            }
            for key, record in self._records.items()
        }
        directory = os.path.dirname(self._path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as fh:
            json.dump(raw, fh, ensure_ascii=False)

    @staticmethod
    def _encode(result):
        if isinstance(result, TruncatedResult):
            return {
                _TRUNCATED_MARKER_KEY: True,
                "size": result.size,
                "limit": result.limit,
            }
        return result


_TRUNCATED_MARKER_KEY = "__idemkey_truncated__"
