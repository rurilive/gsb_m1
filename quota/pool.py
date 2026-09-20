"""资源配额池：开跑前按预估量申请，申请即扣减。

纯标准库，线程安全。池子总配额固定，申请成功即从可用额度里扣掉；
额度不足直接拒绝，不排队也不等待。

除 acquire 一次性扣减外，还支持 reserve/settle 两段式预留：reserve 先按
预估量占额度，settle 按实际用量结算并退还多占部分；预留可带超时，超时未
结算的由 reclaim_expired 全额自动收回，避免额度泄漏。
"""
import threading
import time


class QuotaExceeded(Exception):
    """可用额度不足以满足本次申请。"""


_OPEN = "open"
_SETTLED = "settled"
_EXPIRED = "expired"


class _Reservation:
    __slots__ = ("amount", "created_at", "state")

    def __init__(self, amount, created_at):
        self.amount = amount
        self.created_at = created_at
        self.state = _OPEN


def _check_amount(amount):
    if isinstance(amount, bool) or not isinstance(amount, int):
        raise TypeError("amount 必须是整数")
    if amount <= 0:
        raise ValueError("amount 必须为正")


class QuotaPool:
    """固定总额度的配额池。

    total 为池子总配额，used 为累计扣减量，available = total - used。
    clock 为可注入的时钟（返回秒的可调用对象），默认 time.monotonic；
    reservation_timeout 为预留超时秒数，None 表示预留永不超时。
    """

    def __init__(self, total, clock=None, reservation_timeout=None):
        if isinstance(total, bool) or not isinstance(total, int):
            raise TypeError("total 必须是整数")
        if total < 0:
            raise ValueError("total 不能为负")
        if reservation_timeout is not None and reservation_timeout <= 0:
            raise ValueError("reservation_timeout 必须为正")
        self._lock = threading.Lock()
        self._total = total
        self._used = 0
        self._clock = clock if clock is not None else time.monotonic
        self._reservation_timeout = reservation_timeout
        self._reservations = {}
        self._next_reservation_id = 1

    @property
    def total(self):
        return self._total

    @property
    def used(self):
        return self._used

    @property
    def available(self):
        return self._total - self._used

    def acquire(self, amount):
        """申请 amount 额度，成功即扣减；不足抛 QuotaExceeded。"""
        _check_amount(amount)
        with self._lock:
            self._reclaim_expired_locked()
            free = self._total - self._used
            if amount > free:
                raise QuotaExceeded("申请 %d 超过可用 %d" % (amount, free))
            self._used += amount

    def reserve(self, amount):
        """预留 amount 额度，返回预留号；不足抛 QuotaExceeded。"""
        _check_amount(amount)
        with self._lock:
            self._reclaim_expired_locked()
            free = self._total - self._used
            if amount > free:
                raise QuotaExceeded("预留 %d 超过可用 %d" % (amount, free))
            reservation_id = self._next_reservation_id
            self._next_reservation_id += 1
            self._reservations[reservation_id] = _Reservation(amount, self._clock())
            self._used += amount
            return reservation_id

    def settle(self, reservation_id, actual):
        """按实际用量结算预留：退还 预留量-actual，返回退还额。

        actual 超过预留量抛 ValueError，账目不变；重复结算或预留已被超时
        回收时为幂等空操作，返回 0，不会重复退款。
        """
        if isinstance(actual, bool) or not isinstance(actual, int):
            raise TypeError("actual 必须是整数")
        if actual < 0:
            raise ValueError("actual 不能为负")
        with self._lock:
            self._reclaim_expired_locked()
            reservation = self._reservations[reservation_id]
            if reservation.state != _OPEN:
                return 0
            if actual > reservation.amount:
                raise ValueError(
                    "实际用量 %d 超过预留量 %d，拒绝结算" % (actual, reservation.amount)
                )
            refund = reservation.amount - actual
            self._used -= refund
            reservation.state = _SETTLED
            return refund

    def reclaim_expired(self):
        """收回所有超时的开放预留（全额退还），返回被收回的预留号列表。"""
        with self._lock:
            return self._reclaim_expired_locked()

    def reservation_state(self, reservation_id):
        """返回预留状态：open / settled / expired。"""
        with self._lock:
            return self._reservations[reservation_id].state

    def _reclaim_expired_locked(self):
        if self._reservation_timeout is None:
            return []
        now = self._clock()
        reclaimed = []
        for reservation_id, reservation in self._reservations.items():
            if (
                reservation.state == _OPEN
                and now - reservation.created_at >= self._reservation_timeout
            ):
                reservation.state = _EXPIRED
                self._used -= reservation.amount
                reclaimed.append(reservation_id)
        return reclaimed

    def utilisation(self):
        """当前额度使用率；total 为 0 时返回 0.0。"""
        if self._total == 0:
            return 0.0
        return self._used / self._total
