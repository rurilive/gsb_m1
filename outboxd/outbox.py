"""事务性发件箱与中继。

业务侧 record() 把事件写进本地发件箱表；中继侧 relay()
扫描待发事件逐条投递，成功标记已发，失败保留待重试。
store / sender / clock 全部注入，进程内无真实 IO。
"""

import threading
import time
import uuid


# 行状态：待发 / 已发 / 死信
STATUS_PENDING = "pending"
STATUS_SENT = "sent"
STATUS_DEAD = "dead"


class MemoryStore:
    """内存发件箱表。

    行字段：seq（自增序号）、aggregate（聚合键，也是分区键）、
    kind、payload、status（pending / sent）。seq 从 1 开始单调递增，
    代表记录序，同一聚合键的事件按 seq 升序即为它们的发生顺序。

    可靠投递附加字段：
    attempts：已尝试投递次数；not_before：下次可投递时刻（退避）；
    lease_owner / lease_until：分区租约持有者与到期时刻。
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
                "not_before": None,
                "lease_owner": None,
                "lease_until": None,
            })
            return seq

    def rows(self):
        """表中全部行（副本），按 seq 升序。"""
        with self._lock:
            return [dict(r) for r in self._rows]

    def pending(self):
        """待发行（副本），按 seq 升序（不含死信）。"""
        with self._lock:
            return [dict(r) for r in self._rows if r["status"] == STATUS_PENDING]

    def get(self, seq):
        """按序号取一行，不存在返回 None。"""
        with self._lock:
            for r in self._rows:
                if r["seq"] == seq:
                    return dict(r)
            return None

    def _find(self, seq):
        for r in self._rows:
            if r["seq"] == seq:
                return r
        return None

    def mark_sent(self, seq, owner=None):
        """把一条标记为已发并释放租约。

        传入 owner 时仅租约持有方可标记，被别人抢走则返回 False；
        不传 owner 时无条件标记（基线行为）。
        """
        with self._lock:
            r = self._find(seq)
            if r is None:
                raise KeyError(seq)
            if owner is not None and r["lease_owner"] != owner:
                return False
            r["status"] = STATUS_SENT
            r["lease_owner"] = None
            r["lease_until"] = None
            return True

    def claim(self, seq, owner, now, lease_seconds):
        """原子认领一条待发行的分区租约，认领成功返回 True。

        行已不在待发、未到退避时刻，或租约仍被他人持有时失败。
        自己持有的租约可以续约，过期租约（lease_until <= now）可被接管。
        """
        with self._lock:
            r = self._find(seq)
            if r is None or r["status"] != STATUS_PENDING:
                return False
            if r["not_before"] is not None and now < r["not_before"]:
                return False
            held = r["lease_owner"]
            if held is not None and held != owner and r["lease_until"] > now:
                return False
            r["lease_owner"] = owner
            r["lease_until"] = now + lease_seconds
            return True

    def schedule_retry(self, seq, owner, not_before):
        """记一次失败并按退避时刻重新排队，释放租约。

        仅租约持有方可操作；租约已易主返回 False。
        """
        with self._lock:
            r = self._find(seq)
            if r is None or r["lease_owner"] != owner:
                return False
            r["attempts"] += 1
            r["not_before"] = not_before
            r["lease_owner"] = None
            r["lease_until"] = None
            return True

    def mark_dead(self, seq, owner):
        """连续失败到上限，移入死信并释放租约。

        仅租约持有方可操作；租约已易主返回 False。
        """
        with self._lock:
            r = self._find(seq)
            if r is None or r["lease_owner"] != owner:
                return False
            r["attempts"] += 1
            r["status"] = STATUS_DEAD
            r["lease_owner"] = None
            r["lease_until"] = None
            return True

    def dead(self):
        """死信行（副本），按 seq 升序。"""
        with self._lock:
            return [dict(r) for r in self._rows if r["status"] == STATUS_DEAD]


class Outbox:
    """发件箱：record() 落库，relay() 投递。

    store: 发件箱表，需实现 MemoryStore 的接口。
    sender: 投递器，send(row) 正常返回视为成功，抛异常视为失败。
    clock: 返回当前时刻的可调用对象，默认 time.monotonic，测试可注入。

    可靠投递参数（均为构造注入）：
    max_attempts：单条最多尝试次数，达到后移入死信；
    base_delay / max_delay：失败退避秒数上下限；
    lease_seconds：分区租约时长，凭注入时钟判定到期，中继不睡眠；
    worker_id：中继实例标识，缺省随机生成，用于租约互斥。
    """

    def __init__(self, store, sender, clock=time.monotonic, *,
                 max_attempts=5, base_delay=1.0, max_delay=30.0,
                 lease_seconds=30.0, worker_id=None):
        self._store = store
        self._sender = sender
        self._clock = clock
        self._max_attempts = max_attempts
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._lease_seconds = lease_seconds
        self._worker_id = worker_id or uuid.uuid4().hex

    def record(self, aggregate, kind, payload):
        """业务侧落库，返回事件序号。"""
        return self._store.append(aggregate, kind, payload)

    def relay(self):
        """投递一轮到期的待发事件，返回本次成功投递的条数。

        全表按 seq 升序扫描，每个聚合键只放行队头：前一条未成功
        （待退避重试）之前，同键后一条不投递；不同聚合键互不阻塞，
        死信条目的同键后续条目可继续。投递前先原子认领分区租约，
        并发中继不会投到同一条。失败按指数退避重排，连续失败到
        max_attempts 移入死信。中继不睡眠，未到退避时刻的条目留待
        下次 relay()，时刻由注入 clock 决定。
        """
        delivered = 0
        now = self._clock()
        blocked = set()
        for row in self._store.pending():
            aggregate = row["aggregate"]
            if aggregate in blocked:
                continue
            seq = row["seq"]
            if not self._store.claim(seq, self._worker_id, now,
                                     self._lease_seconds):
                # 未到退避时刻，或队头租约被他人持有：同键后续条目
                # 一律等待，避免并发中继越过队头造成乱序；行已离开
                # 待发（并发标已发/进死信）则不阻塞，放行新队头。
                current = self._store.get(seq)
                if current is None or current["status"] == STATUS_PENDING:
                    blocked.add(aggregate)
                continue
            claimed = self._store.get(seq)
            try:
                self._sender.send(claimed)
            except Exception:
                if self._fail(claimed, now):
                    blocked.add(aggregate)
                continue
            if self._store.mark_sent(seq, owner=self._worker_id):
                delivered += 1
        return delivered

    def _fail(self, row, now):
        """处理一条投递失败，返回该聚合键是否需要队头阻塞。"""
        seq = row["seq"]
        if row["attempts"] + 1 >= self._max_attempts:
            self._store.mark_dead(seq, self._worker_id)
            return False
        delay = min(self._base_delay * (2 ** row["attempts"]),
                    self._max_delay)
        ok = self._store.schedule_retry(seq, self._worker_id, now + delay)
        return ok
