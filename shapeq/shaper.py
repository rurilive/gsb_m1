"""令牌桶流量整形 + 多租户公平配额。

每个租户一个独立令牌桶，桶容量（突发）与补充速率都可配。
令牌补充完全惰性：不依赖后台线程，以注入时钟的时间差在
每次 acquire / pump / stats 时补算，测试可精确对齐补充点。

公平策略：配额按租户静态切分，桶与队列互相独立。某个租户
打满的只是自己那份令牌，吃不到别人头上；它超出的请求要么
进自己的队列等令牌（等待有上限），要么按 overflow="reject"
立即拒掉。排队请求通过 pump 在时钟推进后取出，结果写在
Ticket 上，调用方无需真实 sleep。
"""

import threading
import time
from collections import deque


# Ticket 状态
READY = "ready"        # 已有令牌，请求可执行
QUEUED = "queued"      # 已入队，等 pump 出结果
REJECTED = "rejected"  # 被拒：策略拒绝或排队会超过等待上限

_POLICIES = ("queue", "reject")


class Ticket:
    """一次请求的凭证；入队的凭证在 pump 后状态会翻转。"""

    __slots__ = ("tenant", "status", "ready_at", "enqueued_at")

    def __init__(self, tenant, status, ready_at, enqueued_at):
        self.tenant = tenant
        self.status = status
        self.ready_at = ready_at        # 可取令牌的时刻（预计/实际）
        self.enqueued_at = enqueued_at  # 入队时刻，未入队为 None

    def __repr__(self):
        return (
            f"Ticket(tenant={self.tenant!r}, status={self.status!r}, "
            f"ready_at={self.ready_at:.3f})"
        )


class TokenBucketShaper:
    """按租户整形的令牌桶限流器。

    capacity: 每租户桶容量（允许的突发大小），必须为正。
    refill_rate: 每秒补充的令牌数（长期平均速率），必须为正。
    overflow: 桶被占满时的策略——
        "queue"（默认）：排队等令牌，预计等待超过 max_wait 则当场拒；
        "reject"：桶满立即拒绝，不排队。
    max_wait: 排队允许的最大等待秒数，必须 >= 0。
    clock: 返回当前时刻的可调用对象，默认 time.monotonic，测试可注入。
    """

    def __init__(
        self,
        capacity,
        refill_rate,
        overflow="queue",
        max_wait=1.0,
        clock=time.monotonic,
    ):
        if capacity <= 0:
            raise ValueError("capacity must be > 0")
        if refill_rate <= 0:
            raise ValueError("refill_rate must be > 0")
        if overflow not in _POLICIES:
            raise ValueError(f"overflow must be one of {_POLICIES}")
        if max_wait < 0:
            raise ValueError("max_wait must be >= 0")
        self._capacity = float(capacity)
        self._refill_rate = float(refill_rate)
        self._overflow = overflow
        self._max_wait = float(max_wait)
        self._clock = clock
        self._lock = threading.Lock()
        # tenant -> [tokens, last_refill, deque[Ticket]]
        # tokens 可为负：入队即预扣令牌，负值是排队请求欠下的债。
        self._tenants = {}
        self._allowed = 0
        self._rejected = 0

    def _state(self, tenant, now):
        """取租户状态并按时间差惰性补令牌（不超过桶容量）。"""
        state = self._tenants.get(tenant)
        if state is None:
            state = [self._capacity, now, deque()]
            self._tenants[tenant] = state
            return state
        elapsed = now - state[1]
        if elapsed > 0:
            refilled = state[0] + elapsed * self._refill_rate
            state[0] = min(refilled, self._capacity)
            state[1] = now
        return state

    def acquire(self, tenant, tokens=1):
        """为租户申请 tokens 个令牌，返回 Ticket。

        没有排队债务且桶里够：立即 READY 并扣令牌；否则按
        overflow 策略入队（QUEUED）或拒绝（REJECTED）。入队即
        预扣（记账为债务），预计等待超过 max_wait 的请求当场
        拒绝，调用方立刻可知结果。
        """
        if tokens <= 0:
            raise ValueError("tokens must be > 0")
        with self._lock:
            now = self._clock()
            state = self._state(tenant, now)
            queue = state[2]

            if not queue and state[0] >= tokens:
                state[0] -= tokens
                self._allowed += 1
                return Ticket(tenant, READY, now, None)

            if self._overflow == "reject":
                self._rejected += 1
                return Ticket(tenant, REJECTED, now, None)

            # tokens 含前面排队者的债务，缺口除以速率即等待时间。
            wait = (tokens - state[0]) / self._refill_rate
            if wait > self._max_wait:
                self._rejected += 1
                return Ticket(tenant, REJECTED, now + wait, None)

            state[0] -= tokens
            ready_at = now + wait
            ticket = Ticket(tenant, QUEUED, ready_at, now)
            queue.append(ticket)
            return ticket

    def pump(self):
        """按注入时钟的当前时刻放行所有到期的排队请求。

        各租户各自 FIFO：预计时刻已到的队首翻成 READY 并计数，
        返回本调用内状态翻转的 Ticket 列表。令牌补充与放行点
        由时钟决定，不做真实等待。
        """
        with self._lock:
            now = self._clock()
            ready = []
            for tenant, state in self._tenants.items():
                state = self._state(tenant, now)
                queue = state[2]
                while queue and now + 1e-12 >= queue[0].ready_at:
                    ticket = queue.popleft()
                    ticket.status = READY
                    ticket.ready_at = now
                    self._allowed += 1
                    ready.append(ticket)
            return ready

    def stats(self):
        """计数快照，返回独立 dict，调用方随便改。

        tokens 按租户给出补充后的剩余令牌（下限 0；已被排队
        预占的债务不算在内，排队总量见 queued）。
        """
        with self._lock:
            now = self._clock()
            per_tenant = {}
            queued = 0
            for tenant, state in self._tenants.items():
                state = self._state(tenant, now)
                per_tenant[tenant] = state[0] if state[0] > 0 else 0.0
                queued += len(state[2])
            return {
                "allowed": self._allowed,
                "rejected": self._rejected,
                "queued": queued,
                "tokens": per_tenant,
            }
