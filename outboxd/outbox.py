"""事务性发件箱与中继。

业务侧 record() 把事件写进本地发件箱表；中继侧 relay()
扫描待发事件逐条投递，成功标记已发，失败保留待重试。
store / sender / clock 全部注入，进程内无真实 IO。
"""

import threading
import time


class MemoryStore:
    """内存发件箱表。

    行字段：seq（自增序号）、aggregate（聚合键，也是分区键）、
    kind、payload、status（pending / sent）。seq 从 1 开始单调递增，
    代表记录序，同一聚合键的事件按 seq 升序即为它们的发生顺序。
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._rows = []
        self._next_seq = 1

    def append(self, aggregate, kind, payload):
        """追加一条待发事件，返回其序号。"""
        with self._lock:
            seq = self._next_seq
            self._next_seq += 1
            self._rows.append({
                "seq": seq,
                "aggregate": aggregate,
                "kind": kind,
                "payload": payload,
                "status": "pending",
            })
            return seq

    def rows(self):
        """表中全部行（副本），按 seq 升序。"""
        with self._lock:
            return [dict(r) for r in self._rows]

    def pending(self):
        """待发行（副本），按 seq 升序。"""
        with self._lock:
            return [dict(r) for r in self._rows if r["status"] == "pending"]

    def get(self, seq):
        """按序号取一行，不存在返回 None。"""
        with self._lock:
            for r in self._rows:
                if r["seq"] == seq:
                    return dict(r)
            return None

    def mark_sent(self, seq):
        """把一条标记为已发。"""
        with self._lock:
            for r in self._rows:
                if r["seq"] == seq:
                    r["status"] = "sent"
                    return
            raise KeyError(seq)


class Outbox:
    """发件箱：record() 落库，relay() 投递。

    store: 发件箱表，需实现 MemoryStore 的接口。
    sender: 投递器，send(row) 正常返回视为成功，抛异常视为失败。
    clock: 返回当前时刻的可调用对象，默认 time.monotonic，测试可注入。
    """

    def __init__(self, store, sender, clock=time.monotonic):
        self._store = store
        self._sender = sender
        self._clock = clock

    def record(self, aggregate, kind, payload):
        """业务侧落库，返回事件序号。"""
        return self._store.append(aggregate, kind, payload)

    def relay(self):
        """扫描待发事件逐条投递，返回本次成功投递的条数。

        成功即标记已发；失败保留待重试，不影响后续条目。
        """
        delivered = 0
        for row in self._store.pending():
            try:
                self._sender.send(row)
            except Exception:
                continue
            self._store.mark_sent(row["seq"])
            delivered += 1
        return delivered
