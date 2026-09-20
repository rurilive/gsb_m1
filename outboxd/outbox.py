"""事务性发件箱与中继。

业务侧 record() 把事件写进本地发件箱表；中继侧 relay()
扫描待发事件逐条投递，成功标记已发，失败保留待重试。
store / sender / clock 全部注入，进程内无真实 IO。

可靠投递语义：
- 待发按 seq 单调推进，relay() 总从最小 seq 的可投递条目开始；
- 同一 aggregate（分区）严格按记录序投递，前一条未成功（含退避
  等待中）或未进死信，后一条不能抢先；
- 失败按指数退避重试，退避时刻由注入时钟判定，不真实 sleep；
- 连续失败到上限移入死信（status="dead"），释放分区并继续处理后面的；
- 并发中继靠租约认领互斥，租约带 TTL，崩溃恢复由 TTL 超时兜底，
  同一条不会被两个中继同时投递。
"""

import threading
import time
import uuid


DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_BACKOFF_BASE = 0.5
DEFAULT_BACKOFF_CAP = 30.0
DEFAULT_LEASE_SECONDS = 30.0


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
                "attempts": 0,
                "not_before": 0.0,
                "last_error": None,
                "lease_owner": None,
                "lease_expires_at": None,
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

    def dead(self):
        """死信行（副本），按 seq 升序。"""
        with self._lock:
            return [dict(r) for r in self._rows if r["status"] == "dead"]

    def get(self, seq):
        """按序号取一行，不存在返回 None。"""
        with self._lock:
            for r in self._rows:
                if r["seq"] == seq:
                    return dict(r)
            return None

    def mark_sent(self, seq):
        """把一条标记为已发，并释放租约。"""
        with self._lock:
            for r in self._rows:
                if r["seq"] == seq:
                    r["status"] = "sent"
                    r["lease_owner"] = None
                    r["lease_expires_at"] = None
                    return
            raise KeyError(seq)

    def claim(self, seq, owner, now, lease_seconds):
        """认领一条待发行的租约，成功返回该行副本，否则返回 None。

        仅当行仍为 pending、已到退避时刻且没有他人持有的有效租约时认领成功；
        同一 owner 可续租（重入）。
        """
        with self._lock:
            for r in self._rows:
                if r["seq"] != seq:
                    continue
                if r["status"] != "pending":
                    return None
                if r["not_before"] > now:
                    return None
                holder = r["lease_owner"]
                if holder is not None and holder != owner \
                        and (r["lease_expires_at"] or 0.0) > now:
                    return None
                r["lease_owner"] = owner
                r["lease_expires_at"] = now + lease_seconds
                return dict(r)
            return None

    def retry_later(self, seq, owner, not_before, error):
        """登记一次失败：attempts 加一，设退避时刻并释放租约。"""
        with self._lock:
            for r in self._rows:
                if r["seq"] == seq:
                    r["attempts"] += 1
                    r["not_before"] = not_before
                    r["last_error"] = error
                    if r["lease_owner"] == owner:
                        r["lease_owner"] = None
                        r["lease_expires_at"] = None
                    return
            raise KeyError(seq)

    def mark_dead(self, seq, owner, error):
        """连续失败到上限的行移入死信，并释放租约。"""
        with self._lock:
            for r in self._rows:
                if r["seq"] == seq:
                    r["attempts"] += 1
                    r["status"] = "dead"
                    r["last_error"] = error
                    if r["lease_owner"] == owner:
                        r["lease_owner"] = None
                        r["lease_expires_at"] = None
                    return
            raise KeyError(seq)


class Outbox:
    """发件箱：record() 落库，relay() 投递。

    store: 发件箱表，需实现 MemoryStore 的接口。
    sender: 投递器，send(row) 正常返回视为成功，抛异常视为失败。
    clock: 返回当前时刻的可调用对象，默认 time.monotonic，测试可注入。
    max_attempts: 最大投递次数，达到后移入死信。
    backoff_base / backoff_cap: 指数退避参数（秒），
        第 n 次失败后等待 base * 2**(n-1)，封顶 cap。
    lease_seconds: 投递租约时长，防止并发中继重复投递同一条。
    """

    def __init__(self, store, sender, clock=time.monotonic,
                 max_attempts=DEFAULT_MAX_ATTEMPTS,
                 backoff_base=DEFAULT_BACKOFF_BASE,
                 backoff_cap=DEFAULT_BACKOFF_CAP,
                 lease_seconds=DEFAULT_LEASE_SECONDS):
        self._store = store
        self._sender = sender
        self._clock = clock
        self._max_attempts = max_attempts
        self._backoff_base = backoff_base
        self._backoff_cap = backoff_cap
        self._lease_seconds = lease_seconds

    def record(self, aggregate, kind, payload):
        """业务侧落库，返回事件序号。"""
        return self._store.append(aggregate, kind, payload)

    def relay(self):
        """按可靠投递语义推进待发事件，返回本次成功投递的条数。

        待发按 seq 单调推进；同一 aggregate 严格按记录序，前一条未完成
        （未成功且仍在退避）时跳过该分区后续条目；失败按指数退避重试，
        连续失败到上限移入死信；条目经租约认领后才投递。
        """
        owner = uuid.uuid4().hex
        now = self._clock()
        delivered = 0
        blocked = set()
        for row in self._store.rows():
            if row["status"] != "pending":
                continue
            aggregate = row["aggregate"]
            if aggregate in blocked:
                continue
            if row["not_before"] > now:
                # 前一条还在退避，本分区后续条目一律不许抢先。
                blocked.add(aggregate)
                continue
            row = self._store.claim(
                row["seq"], owner, now, self._lease_seconds)
            if row is None:
                # 被别的中继租走（或已不在 pending），本分区本轮停在它前面。
                blocked.add(aggregate)
                continue
            try:
                self._sender.send(row)
            except Exception as exc:
                attempts = row["attempts"] + 1
                if attempts >= self._max_attempts:
                    self._store.mark_dead(row["seq"], owner, str(exc))
                    # 分区障碍解除（前一条已进死信），继续后面的。
                    continue
                delay = min(
                    self._backoff_base * 2 ** (attempts - 1),
                    self._backoff_cap)
                self._store.retry_later(
                    row["seq"], owner, now + delay, str(exc))
                blocked.add(aggregate)
                continue
            self._store.mark_sent(row["seq"])
            delivered += 1
        return delivered
