"""令牌桶整形与多租户公平。

与 FixedWindowLimiter 的"挡回去"不同，这里做流量整形：
令牌按固定速率补充、桶容量内的突发直接吸收，超额请求可
以排队等令牌；多租户共用一份后端配额时，每租户另有一只
公平桶，谁都不能顺手吃掉别人的份额。
"""

import threading
import time
from collections import deque


_EPS = 1e-9


class _TokenBucket:
    """惰性补充的令牌桶：读取时才按注入时钟补到当前时刻。"""

    def __init__(self, rate, capacity, clock):
        self._rate = rate
        self._capacity = capacity
        self._clock = clock
        self._tokens = float(capacity)
        self._updated = clock()

    def refill(self):
        now = self._clock()
        elapsed = now - self._updated
        if elapsed > 0:
            self._tokens = min(
                self._capacity, self._tokens + elapsed * self._rate
            )
            self._updated = now

    def can_take(self):
        self.refill()
        return self._tokens + _EPS >= 1.0

    def take(self):
        self._tokens -= 1.0

    @property
    def tokens(self):
        self.refill()
        return self._tokens


class Request:
    """acquire 的结果：granted / queued / rejected 三态。"""

    GRANTED = "granted"
    QUEUED = "queued"
    REJECTED = "rejected"

    REJECT_FULL = "bucket_full"
    REJECT_QUEUE_FULL = "queue_full"
    REJECT_TIMEOUT = "timeout"

    __slots__ = ("tenant", "status", "submitted_at", "ready_at",
                 "reason", "waited")

    def __init__(self, tenant, status, submitted_at, ready_at=None,
                 reason=None, waited=0.0):
        self.tenant = tenant
        self.status = status
        self.submitted_at = submitted_at
        self.ready_at = ready_at
        self.reason = reason
        self.waited = waited

    @property
    def granted(self):
        return self.status == self.GRANTED

    def __repr__(self):
        return (f"Request(tenant={self.tenant!r}, status={self.status!r}"
                f"{'' if self.reason is None else ', reason=' + repr(self.reason)})")


class TokenBucketShaper:
    """两级令牌桶整形器。

    shared_rate / shared_burst：共享后端配额的补充速率（令牌/秒）
        与桶容量（可吸收的突发）。
    tenant_rate / tenant_burst：每个租户的公平份额速率与突发上限；
        放行一个请求要同时从共享桶和该租户桶各取一枚令牌，因此单个
        租户长期至多按 tenant_rate 消耗共享配额，其余租户始终拿得到。
    timeout：超额请求在队列里最多等多久（秒）。0 表示不排队、超额
        立刻拒；默认 0。
    max_queue：每个租户的队列长度上限，None 表示不限。
    clock：注入时钟，默认 time.monotonic。
    """

    def __init__(self, shared_rate, shared_burst,
                 tenant_rate=None, tenant_burst=None,
                 timeout=0.0, max_queue=None, clock=time.monotonic):
        if shared_rate <= 0:
            raise ValueError("shared_rate must be > 0")
        if shared_burst <= 0:
            raise ValueError("shared_burst must be > 0")
        if tenant_rate is None:
            tenant_rate = shared_rate
        if tenant_burst is None:
            tenant_burst = shared_burst
        if tenant_rate <= 0:
            raise ValueError("tenant_rate must be > 0")
        if tenant_burst <= 0:
            raise ValueError("tenant_burst must be > 0")
        if timeout < 0:
            raise ValueError("timeout must be >= 0")
        if max_queue is not None and max_queue < 0:
            raise ValueError("max_queue must be >= 0 or None")

        self._shared = _TokenBucket(shared_rate, shared_burst, clock)
        self._tenant_rate = tenant_rate
        self._tenant_burst = tenant_burst
        self._timeout = timeout
        self._max_queue = max_queue
        self._clock = clock
        self._lock = threading.Lock()
        # tenant -> 公平桶；tenant -> FIFO 队列；_turn 决定 RR 顺序
        self._tenant_buckets = {}
        self._queues = {}
        self._turn = []
        self._granted = 0
        self._rejected = 0
        self._timed_out = 0

    def _tenant_bucket(self, tenant):
        bucket = self._tenant_buckets.get(tenant)
        if bucket is None:
            bucket = _TokenBucket(
                self._tenant_rate, self._tenant_burst, self._clock
            )
            self._tenant_buckets[tenant] = bucket
        return bucket

    def _settle(self, request, status, now, reason=None, waited=0.0):
        request.status = status
        request.ready_at = now
        request.reason = reason
        request.waited = waited
        if status == Request.GRANTED:
            self._granted += 1
        else:
            self._rejected += 1
            if reason == Request.REJECT_TIMEOUT:
                self._timed_out += 1
        return request

    def _pump(self, now):
        """按当前时钟结算队列：先超时回收，再 round-robin 放行。

        每轮每个仍在排队的租户至多放行一个，随后轮转到队尾，
        保证令牌同时够时租户间严格交替、无人插队。
        """
        made_progress = True
        while made_progress:
            made_progress = False
            for tenant in list(self._turn):
                queue = self._queues.get(tenant)
                if not queue:
                    self._turn.remove(tenant)
                    continue
                request = queue[0]
                if now > request.submitted_at + self._timeout:
                    queue.popleft()
                    self._turn.remove(tenant)
                    if queue:
                        self._turn.append(tenant)
                    self._settle(
                        request, Request.REJECTED, now,
                        reason=Request.REJECT_TIMEOUT,
                        waited=now - request.submitted_at,
                    )
                    made_progress = True
                    continue
                bucket = self._tenant_buckets[tenant]
                if self._shared.can_take() and bucket.can_take():
                    self._shared.take()
                    bucket.take()
                    queue.popleft()
                    self._turn.remove(tenant)
                    if queue:
                        self._turn.append(tenant)
                    else:
                        self._queues.pop(tenant, None)
                    self._settle(
                        request, Request.GRANTED, now,
                        waited=now - request.submitted_at,
                    )
                    made_progress = True

    def acquire(self, tenant):
        """请求一个令牌，返回 Request。

        先结算此前排队的请求：旧队列没吃完时新请求只能排在后面。
        即时拿不到且 timeout>0 则进队，否则按 bucket_full 拒掉。
        """
        with self._lock:
            now = self._clock()
            self._pump(now)
            bucket = self._tenant_bucket(tenant)
            queue = self._queues.get(tenant)
            if not queue and self._shared.can_take() and bucket.can_take():
                self._shared.take()
                bucket.take()
                request = Request(tenant, Request.GRANTED, now, ready_at=now)
                self._granted += 1
                return request
            if self._timeout <= 0:
                request = Request(tenant, Request.REJECTED, now,
                                  ready_at=now, reason=Request.REJECT_FULL)
                self._rejected += 1
                return request
            if queue is None:
                queue = self._queues[tenant] = deque()
            if self._max_queue is not None and len(queue) >= self._max_queue:
                request = Request(tenant, Request.REJECTED, now,
                                  ready_at=now,
                                  reason=Request.REJECT_QUEUE_FULL)
                self._rejected += 1
                return request
            request = Request(tenant, Request.QUEUED, now)
            queue.append(request)
            if tenant not in self._turn:
                self._turn.append(tenant)
            return request

    def pump(self):
        """把时钟推进到"现在"，结算已到期（放行或超时）的排队请求。"""
        with self._lock:
            self._pump(self._clock())

    def stats(self):
        """计数与水位快照，返回独立 dict，调用方随便改。"""
        with self._lock:
            self._pump(self._clock())
            return {
                "tokens": int(self._shared.tokens + _EPS),
                "granted": self._granted,
                "rejected": self._rejected,
                "timed_out": self._timed_out,
                "waiting": sum(len(q) for q in self._queues.values()),
                "queues": {t: len(q) for t, q in self._queues.items()},
                "tenants": len(self._tenant_buckets),
            }
