"""资源配额池：开跑前按预估量申请，申请即扣减。

纯标准库，线程安全。池子总配额固定，申请成功即从可用额度里扣掉；
额度不足直接拒绝，不排队也不等待。扣掉的额度不区分是否真的用完。
"""
import threading


class QuotaExceeded(Exception):
    """可用额度不足以满足本次申请。"""


class QuotaPool:
    """固定总额度的配额池。

    total 为池子总配额，used 为累计扣减量，available = total - used。
    """

    def __init__(self, total):
        if isinstance(total, bool) or not isinstance(total, int):
            raise TypeError("total 必须是整数")
        if total < 0:
            raise ValueError("total 不能为负")
        self._lock = threading.Lock()
        self._total = total
        self._used = 0

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
        if isinstance(amount, bool) or not isinstance(amount, int):
            raise TypeError("amount 必须是整数")
        if amount <= 0:
            raise ValueError("amount 必须为正")
        with self._lock:
            free = self._total - self._used
            if amount > free:
                raise QuotaExceeded("申请 %d 超过可用 %d" % (amount, free))
            self._used += amount

    def utilisation(self):
        """当前额度使用率；total 为 0 时返回 0.0。"""
        if self._total == 0:
            return 0.0
        return self._used / self._total
