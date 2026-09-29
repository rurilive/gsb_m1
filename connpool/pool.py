"""进程内连接池（改造前的朴素基线）。

一次取一个连接，用完归还：池里有空闲就复用，没有空闲且未达上限就新建，
达到上限时阻塞等待归还。所有操作由一把锁与条件变量保护。
"""

import threading
import time
from collections import deque


class Connection:
    """一条连接：带序号与创建时刻，可做健康标记与关闭。

    健康状态由 is_healthy 汇总：被标记不健康或已关闭都算不健康。
    """

    def __init__(self, cid, created_at=0.0):
        self._cid = cid
        self._created_at = created_at
        self._closed = False
        self._healthy = True

    def __repr__(self):
        return f"<Connection #{self._cid}>"

    @property
    def cid(self):
        """连接序号，同一个池内不重复。"""
        return self._cid

    @property
    def created_at(self):
        """连接创建时的时钟读数。"""
        return self._created_at

    @property
    def closed(self):
        """连接是否已被关闭。"""
        return self._closed

    def is_healthy(self):
        """连接是否可用：未关闭且未被标记不健康。"""
        return (not self._closed) and self._healthy

    def mark_unhealthy(self):
        """把连接标记为不健康，之后 is_healthy 恒为假。"""
        self._healthy = False

    def close(self):
        """关闭连接，之后 is_healthy 恒为假。"""
        self._closed = True


class ConnectionPool:
    """固定上限的连接池：借出、归还，复用空闲连接。

    max_size: 池内同时存在的连接上限。
    factory: 可选，建造新连接的可调用对象；缺省由池自己造 Connection。
    clock: 返回当前时刻的可调用对象，默认 time.monotonic。
    """

    def __init__(self, max_size, factory=None, clock=time.monotonic):
        if max_size < 1:
            raise ValueError("max_size must be >= 1")
        self._max_size = max_size
        self._factory = factory
        self._clock = clock
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._idle = deque()
        self._in_use = set()
        self._active = 0
        self._created = 0

    @property
    def max_size(self):
        """最大连接数。"""
        return self._max_size

    def acquire(self):
        """借出一条连接；池满且无空闲时阻塞，直到有人归还。"""
        with self._cond:
            while True:
                if self._idle:
                    conn = self._idle.popleft()
                    self._active += 1
                    self._in_use.add(id(conn))
                    return conn
                if self._active + len(self._idle) < self._max_size:
                    conn = self._new_connection()
                    self._active += 1
                    self._in_use.add(id(conn))
                    return conn
                self._cond.wait()

    def release(self, conn):
        """归还一条借出的连接，唤醒等待者。"""
        with self._cond:
            if id(conn) not in self._in_use:
                raise ValueError("connection was not borrowed from this pool")
            self._in_use.discard(id(conn))
            self._idle.append(conn)
            self._active -= 1
            self._cond.notify()

    def stats(self):
        """计数快照，返回独立 dict。"""
        with self._lock:
            return {
                "active": self._active,
                "idle": len(self._idle),
                "created": self._created,
            }

    def _new_connection(self):
        # 只在持锁时调用：造一条连接并把创建计数加一。
        if self._factory is None:
            conn = Connection(self._created, self._clock())
        else:
            conn = self._factory()
        self._created += 1
        return conn
