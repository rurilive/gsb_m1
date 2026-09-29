"""朴素本地线程锁。

用一把 threading.Lock 做互斥：acquire 直接尝试拿本地锁，拿到就把锁定为
已持有并记下持有者，release 交给持有者把锁放开。没有任何跨进程协调，
没有消息、没有队列、没有逻辑时钟，只在同一个解释器内有效。
"""

import threading


class LocalLock:
    """本地互斥器：同一时刻只允许一个线程持有。

    持有者标识由 acquire 传入，仅用于记录和校验 release 的人是不是本人。
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._owner = None

    def acquire(self, owner):
        """尝试获取锁。

        用非阻塞方式拿本地锁，拿到就记下 owner 并返回 True；
        锁已被别人持有则返回 False，不等待。
        """
        if not self._lock.acquire(blocking=False):
            return False
        self._owner = owner
        return True

    def release(self, owner):
        """释放锁。

        只有当前持有者本人能释放：owner 对得上就放开本地锁并返回 True；
        没人持有或 owner 不是本人时返回 False。
        """
        if self._owner != owner:
            return False
        self._owner = None
        self._lock.release()
        return True

    def holder(self):
        """返回当前持有者，没人持有则为 None。"""
        return self._owner

    def is_locked(self):
        """锁是否正被持有。"""
        return self._owner is not None
