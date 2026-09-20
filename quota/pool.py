"""资源配额池：支持申请即扣减与预留后按实结算。

纯标准库，线程安全。池子总配额固定，有两条使用路径：

1. ``acquire`` 开跑前按预估量申请，申请即扣减，不区分是否真的用完；
2. ``reserve`` 预留额度并在 ``settle`` 时按实际消耗结算，差额退还，
   重复结算不会多退，超时未结算的预留自动收回。

账目恒等式：``used + reserved == total - available``；
已结算任务的消耗计入 ``used``，在途预留计入 ``reserved``。
"""
import threading
import time


class QuotaExceeded(Exception):
    """可用额度不足以满足本次申请。"""


class ReservationError(Exception):
    """预留结算相关错误的基类。"""


class ReservationNotFound(ReservationError):
    """传入了不属于本池或未知的预留凭证。"""


class ReservationExpired(ReservationError):
    """预留已超时，额度已被回收，不能再结算。"""


class Reservation:
    """``QuotaPool.reserve`` 返回的预留凭证，不透明句柄。"""

    __slots__ = ("id", "amount", "deadline")

    def __init__(self, reservation_id, amount, deadline):
        self.id = reservation_id
        self.amount = amount
        self.deadline = deadline

    def __repr__(self):
        return "Reservation(id=%r, amount=%d, deadline=%r)" % (
            self.id,
            self.amount,
            self.deadline,
        )


class QuotaPool:
    """固定总额度的配额池。

    total 为池子总配额，used 为已结算的实际消耗，reserved 为在途预留，
    available = total - used - reserved。

    clock 为可注入的无参时钟，返回单调递增的数值，默认取 time.monotonic；
    测试可传入受控时钟以精确断言超时。
    """

    def __init__(self, total, *, clock=time.monotonic):
        if isinstance(total, bool) or not isinstance(total, int):
            raise TypeError("total 必须是整数")
        if total < 0:
            raise ValueError("total 不能为负")
        if not callable(clock):
            raise TypeError("clock 必须可调用")
        self._lock = threading.Lock()
        self._total = total
        self._used = 0
        self._reserved = 0
        self._clock = clock
        self._reservations = {}
        self._next_id = 0
        self._reaper_thread = None
        self._reaper_stop = None
        self._reaper_interval = None

    @property
    def total(self):
        return self._total

    @property
    def used(self):
        return self._used

    @property
    def available(self):
        return self._total - self._used - self._reserved

    @property
    def reserved(self):
        """在途预留总额（尚未结算、尚未超时回收）。"""
        return self._reserved

    def acquire(self, amount):
        """申请 amount 额度，成功即扣减；不足抛 QuotaExceeded。"""
        if isinstance(amount, bool) or not isinstance(amount, int):
            raise TypeError("amount 必须是整数")
        if amount <= 0:
            raise ValueError("amount 必须为正")
        with self._lock:
            free = self._total - self._used - self._reserved
            if amount > free:
                raise QuotaExceeded("申请 %d 超过可用 %d" % (amount, free))
            self._used += amount

    def reserve(self, amount, ttl):
        """预留 amount 额度，ttl 为有效时长（时钟单位），返回 Reservation。

        预留期间额度冻结在 reserved 中；超过 deadline 仍未结算会在
        下一次 reserve/settle/reap_expired 或后台 reaper 扫描时自动收回。
        可用不足抛 QuotaExceeded，ttl 必须为正。
        """
        if isinstance(amount, bool) or not isinstance(amount, int):
            raise TypeError("amount 必须是整数")
        if amount <= 0:
            raise ValueError("amount 必须为正")
        if isinstance(ttl, bool) or not isinstance(ttl, (int, float)):
            raise TypeError("ttl 必须是数字")
        if ttl <= 0:
            raise ValueError("ttl 必须为正")
        with self._lock:
            self._reap_expired_locked()
            free = self._total - self._used - self._reserved
            if amount > free:
                raise QuotaExceeded("预留 %d 超过可用 %d" % (amount, free))
            self._next_id += 1
            reservation_id = self._next_id
            deadline = self._clock() + ttl
            self._reservations[reservation_id] = {
                "amount": amount,
                "deadline": deadline,
                "state": "active",
            }
            self._reserved += amount
        return Reservation(reservation_id, amount, deadline)

    def settle(self, reservation, consumed):
        """按实际消耗结算预留，返回退还的额度。

        consumed 为实际用量，必须满足 0 <= consumed <= 预留量，
        退还 amount - consumed，consumed 计入 used。重复结算幂等，
        返回 0 且账目不再变动；超时预留已被全额回收，再结算抛
        ReservationExpired；消耗超过预留量抛 ValueError，绝不凭空多退。
        """
        if not isinstance(reservation, Reservation):
            raise TypeError("reservation 必须是 Reservation 凭证")
        if isinstance(consumed, bool) or not isinstance(
            consumed, (int, float)
        ):
            raise TypeError("consumed 必须是数字")
        if consumed < 0:
            raise ValueError("consumed 不能为负")
        with self._lock:
            record = self._reservations.get(reservation.id)
            if record is None:
                raise ReservationNotFound("预留 %r 不存在" % reservation.id)
            if record["state"] == "settled":
                return 0
            if record["deadline"] <= self._clock():
                self._reap_expired_locked()
                raise ReservationExpired(
                    "预留 %r 已超时回收" % reservation.id
                )
            amount = record["amount"]
            if consumed > amount:
                raise ValueError(
                    "实际消耗 %d 超过预留 %d，拒绝多退" % (consumed, amount)
                )
            record["state"] = "settled"
            record["consumed"] = consumed
            self._reserved -= amount
            self._used += consumed
            return amount - consumed

    def reap_expired(self):
        """回收所有已超时的活跃预留，返回本次回收的额度。"""
        with self._lock:
            return self._reap_expired_locked()

    def _reap_expired_locked(self):
        now = self._clock()
        reclaimed = 0
        for reservation_id, record in self._reservations.items():
            if record["state"] == "active" and record["deadline"] <= now:
                record["state"] = "expired"
                amount = record["amount"]
                self._reserved -= amount
                reclaimed += amount
        return reclaimed

    def start_reaper(self, interval):
        """启动后台守护线程，每 interval（秒）扫描一次超时预留。

        重复调用只保留先启动的那一个。stop_reaper 可停止它。
        """
        if isinstance(interval, bool) or not isinstance(
            interval, (int, float)
        ):
            raise TypeError("interval 必须是数字")
        if interval <= 0:
            raise ValueError("interval 必须为正")
        with self._lock:
            if self._reaper_thread is not None and self._reaper_thread.is_alive():
                return self._reaper_thread
            self._reaper_stop = threading.Event()
            self._reaper_interval = interval
            thread = threading.Thread(
                target=self._reap_loop,
                args=(self._reaper_stop, interval),
                name="quota-reaper",
                daemon=True,
            )
            self._reaper_thread = thread
        thread.start()
        return thread

    def stop_reaper(self):
        """停止后台回收线程，停止前再做一次回收。"""
        with self._lock:
            thread = self._reaper_thread
            stop = self._reaper_stop
        if stop is None:
            return
        stop.set()
        if thread is not None:
            thread.join()

    def _reap_loop(self, stop, interval):
        while not stop.wait(interval):
            self.reap_expired()
        self.reap_expired()

    def utilisation(self):
        """当前额度使用率；total 为 0 时返回 0.0。"""
        if self._total == 0:
            return 0.0
        return self._used / self._total
