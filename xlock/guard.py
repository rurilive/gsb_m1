"""ResourceGuard：批处理任务拿锁保护共享资源的入口。

每个资源一个锁文件，hold 返回 Lease，放进 with 块里用。同一个 guard
里对同一资源可以嵌套持有很多层，最外层退出时才真正释放。
"""

import os

from .env import FileOps, ProcEnv
from .lockfile import FileLock, LockTimeout


class Lease:
    """一次持有的凭据，出 with 块自动释放。"""

    __slots__ = ("resource", "guard", "_done")

    def __init__(self, guard, resource):
        self.resource = resource
        self.guard = guard
        self._done = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()
        return False

    def release(self):
        """释放本次持有，重复调用没有副作用。"""
        if not self._done:
            self._done = True
            self.guard._release(self.resource)

    def __repr__(self):
        return "Lease(%r)" % (self.resource,)


class ResourceGuard:
    """按名字保护一批共享资源。

    lock_dir    锁文件目录，不存在会建
    timeout     hold 的默认超时，None 表示一直等
    poll        等锁的重试间隔
    steal_after 透传给 FileLock
    proc / fs   可注入的环境
    """

    def __init__(self, lock_dir, timeout=None, poll=0.05, steal_after=None,
                 proc=None, fs=None):
        self.lock_dir = lock_dir
        self.timeout = timeout
        self.poll = poll
        self.steal_after = steal_after
        self.proc = proc or ProcEnv()
        self.fs = fs or FileOps()
        self._locks = {}
        self._depth = {}
        self._events = []
        if not os.path.isdir(lock_dir):
            os.makedirs(lock_dir, exist_ok=True)

    # ---- 对外接口 ----

    def path(self, name):
        """资源 name 的锁文件路径。"""
        return os.path.join(self.lock_dir, name + ".lock")

    def hold(self, name, timeout=None):
        """拿资源 name 的锁，返回 Lease，超时抛 LockTimeout。"""
        lock = self._lock(name)
        if self._depth.get(name, 0) > 0 or lock.is_mine():
            # 已经拿着了，直接复用
            self._depth[name] = self._depth.get(name, 0) + 1
            self._record("enter", name)
            return Lease(self, name)
        if not lock.acquire(timeout):
            raise LockTimeout("resource %r is busy" % (name,))
        self._depth[name] = 1
        self._record("enter", name)
        return Lease(self, name)

    def is_held(self, name):
        """资源现在有没有人持着。"""
        return self._lock(name).is_held()

    def owner(self, name):
        """资源现在的持有者信息，没人拿着返回 None。"""
        return self._lock(name).owner()

    def events(self):
        """本 guard 的进出流水：(序号, 事件, 资源, pid, 时间)。"""
        return list(self._events)

    # ---- 内部实现 ----

    def _lock(self, name):
        lock = self._locks.get(name)
        if lock is None:
            lock = FileLock(self.path(name), timeout=self.timeout,
                            poll=self.poll, steal_after=self.steal_after,
                            proc=self.proc, fs=self.fs)
            self._locks[name] = lock
        return lock

    def _release(self, name):
        depth = self._depth.get(name, 0) - 1
        if depth < 0:
            return
        self._depth[name] = depth
        self._record("exit", name)
        if depth == 0:
            self._lock(name).release()

    def _record(self, event, name):
        self._events.append((len(self._events) + 1, event, name,
                             self.proc.pid(), self.proc.wall()))
