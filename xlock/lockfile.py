"""基于锁文件的跨进程互斥。

锁文件放在约定目录里，内容记录持有者的进程号和拿锁时间；创建锁文件
就是持有，删掉就是释放。批处理任务用它保护共享资源。
"""

from .env import FileOps, ProcEnv


class LockTimeout(RuntimeError):
    """超时时间内没拿到锁。"""


class LockInfo:
    """锁文件里记录的持有者信息。"""

    __slots__ = ("pid", "at")

    def __init__(self, pid, at):
        self.pid = pid
        self.at = at

    def __repr__(self):
        return "LockInfo(pid=%r, at=%r)" % (self.pid, self.at)


def encode_info(info):
    """持有者信息序列化成锁文件内容。"""
    return ("pid=%d at=%.6f\n" % (info.pid, info.at)).encode("ascii")


def decode_info(data):
    """解析锁文件内容，格式不对返回 None。"""
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError:
        return None
    fields = {}
    for chunk in text.split():
        key, sep, value = chunk.partition("=")
        if not sep or key in fields:
            return None
        fields[key] = value
    try:
        return LockInfo(int(fields["pid"]), float(fields["at"]))
    except (KeyError, ValueError):
        return None


class FileLock:
    """一把按路径的跨进程锁。

    path        锁文件路径
    timeout     acquire 的默认超时，None 表示一直等
    poll        等锁时的重试间隔（秒）
    steal_after 锁文件存在超过这么多秒才允许接管，None 表示不接管
    proc, fs    可注入的进程与文件操作
    """

    def __init__(self, path, timeout=None, poll=0.05, steal_after=None,
                 proc=None, fs=None):
        self.path = path
        self.timeout = timeout
        self.poll = poll
        self.steal_after = steal_after
        self.proc = proc or ProcEnv()
        self.fs = fs or FileOps()

    # ---- 对外接口 ----

    def acquire(self, timeout=None):
        """拿锁，拿到返回 True，超时返回 False。"""
        if timeout is None:
            timeout = self.timeout
        deadline = None
        if timeout is not None:
            deadline = self.proc.monotonic() + float(timeout)
        while True:
            if self.fs.create_exclusive(self.path, encode_info(self._mine())):
                return True
            if self._may_steal():
                self.fs.overwrite(self.path, encode_info(self._mine()))
                return True
            if deadline is not None and self.proc.monotonic() >= deadline:
                return False
            self.proc.sleep(self.poll)

    def release(self):
        """释放锁：把锁文件删掉。"""
        self.fs.remove(self.path)

    def is_mine(self):
        """锁文件里记的是不是本进程。"""
        info = self.owner()
        return info is not None and info.pid == self.proc.pid()

    def is_held(self):
        """现在有没有人拿着。"""
        return self.owner() is not None

    def owner(self):
        """读锁文件的持有者信息，没有或者读不出返回 None。"""
        data = self.fs.read(self.path)
        if data is None:
            return None
        return decode_info(data)

    # ---- 内部实现 ----

    def _mine(self):
        return LockInfo(self.proc.pid(), self.proc.wall())

    def _may_steal(self):
        if self.steal_after is None:
            return False
        mtime = self.fs.mtime(self.path)
        if mtime is None:
            return False
        return self.proc.wall() - mtime > self.steal_after
