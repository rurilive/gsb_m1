"""事务性发件箱与可靠中继。

业务侧 record() 把事件写进本地发件箱表；中继侧 relay()
扫描待发事件逐条投递：成功标记已发，失败按指数退避重试，
连续失败到上限移入死信，并发中继靠租约互斥认领。
store / sender / clock 全部注入，进程内无真实 IO。
"""

import threading
import time


class MemoryStore:
    """内存发件箱表。

    行字段：seq（自增序号）、aggregate（聚合键，也是分区键）、
    kind、payload、status（pending / sent / dead）、attempts
    （连续失败次数）、next_attempt_at（下次可投递时刻）、
    lease_owner / lease_until（租约持有者与到期时刻）。
    seq 从 1 开始单调递增，代表记录序，同一聚合键的事件
    按 seq 升序即为它们的发生顺序。
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
                "attempts": 0,
                "next_attempt_at": 0.0,
                "lease_owner": None,
                "lease_until": 0.0,
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

    def claim(self, seq, owner, now, ttl):
        """认领一行的租约，成功返回 True，被他人持有则返回 False。"""
        with self._lock:
            for r in self._rows:
                if r["seq"] != seq:
                    continue
                if r["status"] != "pending":
                    return False
                if r["lease_until"] > now and r["lease_owner"] != owner:
                    return False
                r["lease_owner"] = owner
                r["lease_until"] = now + ttl
                return True
            raise KeyError(seq)

    def release(self, seq, owner):
        """释放自己持有的租约。"""
        with self._lock:
            for r in self._rows:
                if r["seq"] == seq and r["lease_owner"] == owner:
                    r["lease_owner"] = None
                    r["lease_until"] = 0.0
                    return

    def note_failure(self, seq, next_attempt_at):
        """记一次投递失败：连续失败数加一，并排定下次可投递时刻。"""
        with self._lock:
            for r in self._rows:
                if r["seq"] == seq:
                    r["attempts"] += 1
                    r["next_attempt_at"] = next_attempt_at
                    return
            raise KeyError(seq)

    def mark_dead(self, seq):
        """把一条移入死信，不再投递，也不再阻塞同聚合键的后续事件。"""
        with self._lock:
            for r in self._rows:
                if r["seq"] == seq:
                    r["status"] = "dead"
                    return
            raise KeyError(seq)

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
    """发件箱：record() 落库，relay() 可靠投递。

    store: 发件箱表，需实现 MemoryStore 的接口。
    sender: 投递器，send(row) 正常返回视为成功，抛异常视为失败。
    clock: 返回当前时刻的可调用对象，默认 time.monotonic，测试可注入。
    max_attempts: 单条连续失败上限，达到即移入死信。
    base_backoff: 退避基数（秒），第 n 次失败后等待 base * 2 ** (n - 1)。
    lease_ttl: 租约时长（秒），持有者崩溃后租约到期他人才可接管。
    owner: 本中继实例的租约标识，默认按实例生成。
    """

    def __init__(self, store, sender, clock=time.monotonic,
                 max_attempts=5, base_backoff=1.0, lease_ttl=30.0,
                 owner=None):
        self._store = store
        self._sender = sender
        self._clock = clock
        self._max_attempts = max_attempts
        self._base_backoff = base_backoff
        self._lease_ttl = lease_ttl
        self._owner = owner if owner is not None else "outbox-%x" % id(self)

    def record(self, aggregate, kind, payload):
        """业务侧落库，返回事件序号。"""
        return self._store.append(aggregate, kind, payload)

    def relay(self):
        """扫描待发事件逐条投递，返回本次成功投递的条数。

        同一聚合键严格按 seq 升序投递：前一条未成功（重试中或
        被他人租用），后一条不抢先；前一条进死信后才放行后续。
        失败按指数退避排定下次投递时刻，连续失败到上限移死信。
        投递前先认领租约，并发中继不会重复投递同一条。
        """
        now = self._clock()
        delivered = 0
        blocked = set()
        for row in self._store.pending():
            aggregate = row["aggregate"]
            if aggregate in blocked:
                continue
            if row["next_attempt_at"] > now:
                blocked.add(aggregate)
                continue
            if not self._store.claim(row["seq"], self._owner, now, self._lease_ttl):
                blocked.add(aggregate)
                continue
            try:
                self._sender.send(row)
            except Exception:
                attempts = row["attempts"] + 1
                delay = self._base_backoff * 2 ** (attempts - 1)
                self._store.note_failure(row["seq"], now + delay)
                if attempts >= self._max_attempts:
                    self._store.mark_dead(row["seq"])
                else:
                    blocked.add(aggregate)
            else:
                self._store.mark_sent(row["seq"])
                delivered += 1
            finally:
                self._store.release(row["seq"], self._owner)
        return delivered
