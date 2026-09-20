"""按优先级发放租约的公平分配器。

请求按优先级排队，优先级数字越小越优先；久等的请求会被提到
队首，避免低优先级在高优先级持续涌入时被一直压着。时钟可注入，
方便做确定性的时间断言。
"""

import time


class Request:
    """一条排队中的租约请求。"""

    __slots__ = ("ticket", "node", "prio", "arrival", "timeout", "cancelled")

    def __init__(self, ticket, node, prio, arrival, timeout):
        self.ticket = ticket
        self.node = node
        self.prio = prio
        self.arrival = arrival
        self.timeout = timeout
        self.cancelled = False


class FairLease:
    """一个租约发放器，同时只发一条租约，队列由优先级和等待时长决定顺序。

    clock: 返回当前时刻的可调用对象，默认 time.monotonic，测试可注入。
    aging: 老化窗口秒数，请求等待达到这个时长后会被提到队首。
    """

    def __init__(self, clock=time.monotonic, aging=5.0):
        if aging <= 0:
            raise ValueError("aging must be > 0")
        self._clock = clock
        self._aging = float(aging)
        # ticket -> Request，ticket 单调递增，天然记录先来后到
        self._queue = {}
        self._next_ticket = 1

    def request(self, node, prio, timeout=None):
        """登记一条请求，返回它唯一的凭据 ticket。

        prio 越小越优先；timeout 是最长等待秒数，None 表示不设上限。
        """
        ticket = self._next_ticket
        self._next_ticket += 1
        self._queue[ticket] = Request(ticket, node, prio,
                                      self._clock(), timeout)
        return ticket

    def cancel(self, ticket):
        """撤销一条尚未发放的请求，返回是否真的撤掉。"""
        req = self._queue.get(ticket)
        if req is None:
            return False
        req.cancelled = True
        return True

    def pending(self):
        """当前仍会参与下一轮发放的 node 列表，按服务顺序排列。"""
        return [req.node for req in self._order(self._clock())]

    def grant(self):
        """发放一条租约，返回拿到的 node；没有可发放的请求时返回 None。"""
        ordered = self._order(self._clock())
        if not ordered:
            return None
        req = ordered[0]
        del self._queue[req.ticket]
        return req.node

    # ---- 内部 ----

    def _live(self, now):
        """清掉已经超时的请求，返回队列里剩下的请求。"""
        for ticket, req in list(self._queue.items()):
            if req.timeout is not None and (now - req.arrival) >= req.timeout:
                del self._queue[ticket]
        return list(self._queue.values())

    def _order(self, now):
        """给出这一轮的服务顺序，等得久的会得到照顾。"""
        return sorted(self._live(now), key=lambda req: (req.prio, req.node))
