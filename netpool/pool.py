"""进程内连接池，多线程安全。

连接对象由调用方注入的 factory 创建（本包用 FakeConn 模拟，接口与真实
socket 一致：close() / healthy 属性）。语义约定见 README，本文件与 README
如有出入，以 README 为准。
"""

import itertools
import threading
import time


class PoolClosedError(Exception):
    """池已关闭后再借/还。"""


class BorrowTimeout(Exception):
    """在 timeout 时间内没等到可用连接。"""


class FakeConn:
    """模拟连接。healthy 置 False 表示下游探测发现它坏了。"""

    _ids = itertools.count(1)

    def __init__(self):
        self.cid = next(self._ids)
        self.closed = False
        self.healthy = True

    def close(self):
        self.closed = True

    def __repr__(self):
        return "<FakeConn #%d%s>" % (self.cid, " closed" if self.closed else "")


class ConnectionPool:
    """固定上限的连接池。

    - borrow(timeout)：有空闲拿空闲；池未满建新的；否则等别的协程归还，
      最多等 timeout 秒，到点抛 BorrowTimeout
    - return_conn(conn)：归还进空闲队列
    - close()：关闭池，空闲连接全部关掉，等待者立即收到 PoolClosedError
    """

    def __init__(self, factory=None, max_size=4, borrow_timeout=1.0):
        if max_size < 1:
            raise ValueError("max_size must be >= 1")
        self._factory = factory or (lambda seq: FakeConn())
        self._max_size = max_size
        self._borrow_timeout = borrow_timeout
        self._idle = []
        self._inflight = set()
        self._cond = threading.Condition()
        self._closed = False
        self._created = 0

    @property
    def max_size(self):
        return self._max_size

    def stats(self):
        with self._cond:
            return {
                "idle": len(self._idle),
                "inflight": len(self._inflight),
                "created": self._created,
                "closed": self._closed,
            }

    def borrow(self, timeout=None):
        if timeout is None:
            timeout = self._borrow_timeout
        with self._cond:
            if self._closed:
                raise PoolClosedError("pool is closed")
            if self._idle:
                conn = self._idle.pop()
                self._inflight.add(conn)
                return conn
            if len(self._inflight) < self._max_size:
                conn = self._factory(self._created)
                self._created += 1
                self._inflight.add(conn)
                return conn
            # 池满，等归还
            deadline = time.monotonic() + timeout
            self._cond.wait(timeout)
            if self._idle:
                conn = self._idle.pop()
                self._inflight.add(conn)
                return conn
            if self._closed:
                raise PoolClosedError("pool is closed")
            if time.monotonic() >= deadline:
                raise BorrowTimeout("no connection within %.3fs" % timeout)
            # 没到 deadline 却什么都没拿到——回到上面重查一次
            if self._idle:
                conn = self._idle.pop()
                self._inflight.add(conn)
                return conn
            raise BorrowTimeout("no connection within %.3fs" % timeout)

    def return_conn(self, conn):
        with self._cond:
            if conn not in self._inflight:
                raise ValueError("connection not borrowed from this pool")
            self._inflight.discard(conn)
            if self._closed:
                conn.close()
                return
            self._idle.append(conn)
            self._cond.notify_all()

    def close(self):
        with self._cond:
            if self._closed:
                return
            self._closed = True
            while self._idle:
                self._idle.pop().close()
            # 等待中的 borrow 会在下次被唤醒时看到 _closed
