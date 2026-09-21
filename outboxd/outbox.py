"""事务性发件箱与可靠中继。

业务侧 record() 把事件写进本地发件箱表；中继侧 relay()
按 seq 单调扫描待发事件：租约认领后投递，成功标记已发，
失败按退避计划重试，连续失败到上限移入死信。同一聚合键
严格按记录序投递，前一条未成功则后续条目本轮不抢先。
store / sender / clock 全部注入，进程内无真实 IO。
"""

import threading
import time


class MemoryStore:
    """内存发件箱表。

    行字段：seq（自增序号）、aggregate（聚合键，也是分区键）、
    kind、payload、status（pending / sent / dead）、attempts
    （连续失败次数）、next_attempt_at（下次可投递时刻）、
    lease_owner / lease_until（租约持有者与其过期时刻）。
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
                "lease_until": None,
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

    def claim(self, seq, owner, now, ttl):
        """认领一条到期的待发行，成功返回行副本，否则返回 None。

        行已被其他持有者租用且租约未过期、状态非待发、或仍处于
        退避期（next_attempt_at 未到）时认领失败。成功则把租约
        续到 now + ttl。
        """
        with self._lock:
            for r in self._rows:
                if r["seq"] != seq:
                    continue
                if r["status"] != "pending" or r["next_attempt_at"] > now:
                    return None
                if (r["lease_until"] is not None and r["lease_until"] > now
                        and r["lease_owner"] != owner):
                    return None
                r["lease_owner"] = owner
                r["lease_until"] = now + ttl
                return dict(r)
            return None

    def mark_sent(self, seq):
        """把一条标记为已发。"""
        with self._lock:
            for r in self._rows:
                if r["seq"] == seq:
                    r["status"] = "sent"
                    r["lease_owner"] = None
                    r["lease_until"] = None
                    return
            raise KeyError(seq)

    def mark_failed(self, seq, attempts, next_attempt_at):
        """记录一次投递失败：累计连续失败次数，设定下次可投递
        时刻，并释放租约。"""
        with self._lock:
            for r in self._rows:
                if r["seq"] == seq:
                    r["attempts"] = attempts
                    r["next_attempt_at"] = next_attempt_at
                    r["lease_owner"] = None
                    r["lease_until"] = None
                    return
            raise KeyError(seq)

    def mark_dead(self, seq, attempts):
        """连续失败到上限，记录失败次数，移入死信并释放租约。"""
        with self._lock:
            for r in self._rows:
                if r["seq"] == seq:
                    r["status"] = "dead"
                    r["attempts"] = attempts
                    r["lease_owner"] = None
                    r["lease_until"] = None
                    return
            raise KeyError(seq)


class Outbox:
    """发件箱：record() 落库，relay() 可靠投递。

    store: 发件箱表，需实现 MemoryStore 的接口。
    sender: 投递器，send(row) 正常返回视为成功，抛异常视为失败。
    clock: 返回当前时刻的可调用对象，默认 time.monotonic，测试可注入。
    max_attempts: 连续失败上限，达到即移入死信。
    backoff_base / backoff_factor / backoff_cap: 退避参数，第 n 次
        连续失败后的等待时长为 min(cap, base * factor ** (n - 1))。
    lease_ttl: 认领租约时长，租约内其他中继无法认领同一条。
    owner: 本中继的租约标识，默认按实例生成，并发中继需各自不同。
    """

    def __init__(self, store, sender, clock=time.monotonic,
                 max_attempts=5, backoff_base=1.0, backoff_factor=2.0,
                 backoff_cap=60.0, lease_ttl=30.0, owner=None):
        self._store = store
        self._sender = sender
        self._clock = clock
        self._max_attempts = max_attempts
        self._backoff_base = backoff_base
        self._backoff_factor = backoff_factor
        self._backoff_cap = backoff_cap
        self._lease_ttl = lease_ttl
        self._owner = owner or "relay-%x" % id(self)

    def record(self, aggregate, kind, payload):
        """业务侧落库，返回事件序号。"""
        return self._store.append(aggregate, kind, payload)

    def relay(self):
        """扫描待发事件逐条投递，返回本次成功投递的条数。

        待发按 seq 单调推进；每条先按租约认领再投递，成功即标记
        已发，失败按退避计划安排重试，连续失败到上限移入死信。
        同一聚合键严格按记录序投递：前一条未成功（退避中、被其他
        中继租用或刚失败）时，同键后续条目本轮一律跳过；不同聚合
        键互不阻塞。
        """
        now = self._clock()
        delivered = 0
        blocked = set()
        for row in self._store.pending():
            aggregate = row["aggregate"]
            if aggregate in blocked:
                continue
            claimed = self._store.claim(
                row["seq"], self._owner, now, self._lease_ttl)
            if claimed is None:
                blocked.add(aggregate)
                continue
            try:
                self._sender.send(claimed)
            except Exception:
                attempts = claimed["attempts"] + 1
                if attempts >= self._max_attempts:
                    self._store.mark_dead(row["seq"], attempts)
                else:
                    self._store.mark_failed(
                        row["seq"], attempts, now + self._backoff(attempts))
                blocked.add(aggregate)
                continue
            self._store.mark_sent(row["seq"])
            delivered += 1
        return delivered

    def _backoff(self, attempts):
        """第 attempts 次连续失败后的退避时长。"""
        return min(self._backoff_cap,
                   self._backoff_base * self._backoff_factor ** (attempts - 1))
