"""幂等键存储：按幂等键记住已处理请求的结果。

上游提交前先用幂等键问一遍要不要干活，干完把结果记回键上；同一个键再
提交时直接把上次的结果回放出去，避免重复扣款。时间读取统一走注入的
clock；记录可以落一份到磁盘，进程重启后接着用。纯标准库实现。

处理中途失败时调用 rollback(key) 放开占用，避免键被半成品占位永久卡死。
长流程可以用 renew(key, ttl=...) 在处理中途或完成后续期。结果体积超过
max_result_size 时只落一份截断标记，取回时能据此识别。
"""

import json
import os
import threading
import time


class _Record:
    """一条幂等记录。

    result 为 None 表示键已经占上但结果还没写回来；finished_at 为 None
    表示这次处理还没收尾。
    """

    __slots__ = ("result", "created_at", "finished_at", "expires_at")

    def __init__(self, result, created_at, finished_at, expires_at=None):
        self.result = result
        self.created_at = created_at
        self.finished_at = finished_at
        # None 表示永不过期；否则为该记录到期的时钟时刻。
        self.expires_at = expires_at


class TruncatedResult:
    """结果超过体积上限时留下的截断标记。

    取回时若拿到本对象（而不是原始结果），说明那份回执没有被完整保存，
    调用方应当走对账/补查而不是把标记当成真实回执回放。
    """

    __slots__ = ("truncated", "original_size", "size_limit")

    def __init__(self, original_size, size_limit):
        self.truncated = True
        self.original_size = original_size
        self.size_limit = size_limit

    def __eq__(self, other):
        return (
            isinstance(other, TruncatedResult)
            and self.original_size == other.original_size
            and self.size_limit == other.size_limit
        )

    def __repr__(self):
        return (
            "TruncatedResult(original_size=%r, size_limit=%r)"
            % (self.original_size, self.size_limit)
        )

    def to_marker(self):
        """落盘用的标记字典。"""
        return {
            "__truncated__": True,
            "original_size": self.original_size,
            "size_limit": self.size_limit,
        }

    @classmethod
    def from_marker(cls, item):
        return cls(item["original_size"], item["size_limit"])


class IdempotencyStore:
    """按幂等键记住请求结果的存储。

    ttl: 记录存活秒数，从请求完成（finish）时刻起算；None 表示永不过期。
    clock: 返回当前时刻的可调用对象，默认 time.monotonic，测试可注入。
    path: 落盘文件路径；None 表示只放在内存里。
    max_result_size: 结果体积上限（JSON 编码后的字节数）；None 表示不限。
        超限的结果只保存一份 TruncatedResult 截断标记，不撑爆缓存。
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
            self._records[key] = _Record(
                None, now, None,
                self._expiry_from(now, self._ttl),
            )
            self._save()
            return True

    def finish(self, key, result):
        """把处理结果记到键上，这个键之后就算已处理。"""
        key = self._normalize(key)
        now = self._clock()
        result = self._truncate_if_needed(result)
        with self._lock:
            record = self._records.get(key)
            if record is None:
                self._records[key] = _Record(
                    result, now, now,
                    self._expiry_from(now, self._ttl),
                )
            else:
                record.result = result
                record.finished_at = now
                # 有效期按完成时刻重新起算，耗时再长也不会“刚收工就过期”。
                record.expires_at = self._expiry_from(now, self._ttl)
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

    def renew(self, key, ttl=None):
        """给键的有效期续期。

        已完成的键从完成时刻（finished_at）起续，处理中的键从当前时刻起
        续，长流程可以中途延长而不必整单重跑。ttl 为 None 时使用构造时
        的默认 ttl；两者都是 None（本就永不过期）时不产生变化。

        返回 True 表示键存在且已续期；False 表示没有这个键。
        """
        if ttl is not None and ttl <= 0:
            raise ValueError("ttl must be positive")
        key = self._normalize(key)
        seconds = self._ttl if ttl is None else ttl
        now = self._clock()
        with self._lock:
            record = self._records.get(key)
            if record is None:
                return False
            if seconds is not None:
                base = record.finished_at if record.finished_at is not None else now
                record.expires_at = base + seconds
                self._save()
            return True

    def rollback(self, key):
        """放开一个只 begin 还没 finish 的占位。

        处理中途失败时调用它，让同一个键之后能重新 begin。只清除“尚未
        完成”的占位；已经 finish 的记录绝不回滚，防止把真实回执抹掉。

        返回 True 表示放开了占位；False 表示没有占位或键已完成。
        """
        key = self._normalize(key)
        with self._lock:
            record = self._records.get(key)
            if record is None or record.finished_at is not None:
                return False
            del self._records[key]
            self._save()
            return True

    # -- 内部实现 --

    def _normalize(self, key):
        """键的规范化：只去掉首尾空白，保留大小写等原始差异。

        单号的大小写差异是两笔真实不同的单子，不能折成同一个键。
        """
        return key.strip()

    def _expiry_from(self, base, ttl):
        """从基准时刻起算的到期时刻；ttl 为 None 时永不过期。"""
        if ttl is None:
            return None
        return base + ttl

    def _truncate_if_needed(self, result):
        """结果超过体积上限时替换成截断标记。"""
        if self._max_result_size is None:
            return result
        if isinstance(result, TruncatedResult):
            return result
        encoded = json.dumps(result, ensure_ascii=False).encode("utf-8")
        if len(encoded) <= self._max_result_size:
            return result
        return TruncatedResult(len(encoded), self._max_result_size)

    def _purge(self, now):
        """清掉已经过期的记录。"""
        expired = [
            key
            for key, record in self._records.items()
            if record.expires_at is not None and now >= record.expires_at
        ]
        for key in expired:
            del self._records[key]

    def _load(self):
        """从磁盘读回上次的记录。"""
        if not os.path.exists(self._path):
            return
        with open(self._path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        now = self._clock()
        for key, item in raw.items():
            result = item["result"]
            if isinstance(result, dict) and result.get("__truncated__"):
                result = TruncatedResult.from_marker(result)
            finished_at = item["finished_at"]
            expires_at = item.get("expires_at")
            if finished_at is None:
                # 落盘时还没收尾的记录来自崩溃/重启的进程，本进程不再
                # 持有那次处理，留着只会把键永久卡死，直接丢弃。
                continue
            if expires_at is None:
                # 兼容旧格式文件：到期时刻按完成时刻补算。
                expires_at = self._expiry_from(finished_at, self._ttl)
            self._records[key] = _Record(
                result, item["created_at"], finished_at, expires_at
            )
        self._purge(now)

    def _save(self):
        """把当前记录写到磁盘。"""
        if self._path is None:
            return
        raw = {
            key: {
                "result": (
                    record.result.to_marker()
                    if isinstance(record.result, TruncatedResult)
                    else record.result
                ),
                "created_at": record.created_at,
                "finished_at": record.finished_at,
                "expires_at": record.expires_at,
            }
            for key, record in self._records.items()
        }
        directory = os.path.dirname(self._path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        tmp_path = "%s.tmp.%s" % (self._path, os.getpid())
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(raw, fh)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, self._path)
