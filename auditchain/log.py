"""审计日志的对外入口。

append 追加一条，序号从 1 开始连着走，每条带一个内容摘要；
read_all 按写入顺序读回。写入走一把锁，多个线程一起写不会串序号。
"""

import threading
import time

from auditchain.codec import record_digest
from auditchain.store import RecordStore


class AuditLog:
    """本地文件的追加型审计日志。

    path: 日志文件路径，不存在就等第一次写入时建。
    clock: 注入时钟，给新记录打时间戳。
    """

    def __init__(self, path, clock=time.time):
        self.path = path
        self._clock = clock
        self._store = RecordStore(path)
        self._lock = threading.Lock()
        self._last = self._load_last()
        self._seq = 0 if self._last is None else int(self._last["seq"])

    def append(self, action, actor="", detail="", ts=None):
        """追加一条审计记录，返回写进去的那条。

        返回的是副本，调用方拿去改不影响日志里的内容。
        """
        with self._lock:
            seq = self._seq + 1
            record = {
                "seq": seq,
                "ts": float(self._clock() if ts is None else ts),
                "action": action,
                "actor": actor,
                "detail": detail,
            }
            record["digest"] = record_digest(record)
            self._store.append(record)
            self._last = record
            self._seq = seq
            return dict(record)

    def read_all(self):
        """按写入顺序读回全部记录。文件坏了抛 CorruptLogError。"""
        entries, _ = self._store.scan()
        return [record for _, record in entries]

    def last(self):
        """最新一条记录的副本，空日志返回 None。"""
        return None if self._last is None else dict(self._last)

    def count(self):
        """记录条数。"""
        return self._seq

    def _load_last(self):
        """开日志时扫一遍，拿到最后一条完整记录。"""
        entries, _ = self._store.scan()
        if not entries:
            return None
        return entries[-1][1]
