"""xlock 的运行环境视图：进程、时钟、锁文件操作。

线上路径用真实实现；测试可以换成假对象，构造想要的时序。
"""

import errno
import os
import time


class ProcEnv:
    """进程信息与时间来源。"""

    def pid(self):
        return os.getpid()

    def alive(self, pid):
        """进程是否还在。"""
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False
        return True

    def identity(self, pid):
        """pid 本轮生命周期的身份指纹，同一个号被复用后值会变，取不到返回 None。"""
        try:
            with open("/proc/%d/stat" % pid, "rb") as fh:
                stat = fh.read()
            with open("/proc/sys/kernel/random/boot_id", "r") as fh:
                boot = fh.read().strip()
        except OSError:
            return None
        cut = stat.rfind(b")")
        if cut < 0:
            return None
        fields = stat[cut + 1:].split()
        if len(fields) < 20:
            return None
        return "%s/%s" % (boot, fields[19].decode("ascii", "replace"))

    def wall(self):
        """墙钟时间，写进锁文件用。"""
        return time.time()

    def monotonic(self):
        """单调钟，算超时用。"""
        return time.monotonic()

    def sleep(self, seconds):
        time.sleep(seconds)


class FileOps:
    """锁文件上的文件操作，默认直接走 os。测试可以换成带延迟、乱序或者
    注入失败的假实现。"""

    def create_exclusive(self, path, data):
        """O_CREAT|O_EXCL 建文件并写入，已存在返回 False。"""
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            return False
        except OSError as exc:
            if exc.errno in (errno.EEXIST, errno.ENOTDIR, errno.EISDIR):
                return False
            raise
        try:
            os.write(fd, data)
        finally:
            os.close(fd)
        return True

    def read(self, path):
        """读锁文件内容，文件不在或读不了返回 None。"""
        try:
            with open(path, "rb") as fh:
                return fh.read()
        except OSError:
            return None

    def overwrite(self, path, data):
        """原地改写锁文件内容，文件不在返回 False。"""
        try:
            fd = os.open(path, os.O_WRONLY | os.O_TRUNC)
        except OSError:
            return False
        try:
            os.write(fd, data)
        finally:
            os.close(fd)
        return True

    def remove(self, path):
        """删掉锁文件，本来就不在返回 False。"""
        try:
            os.unlink(path)
        except FileNotFoundError:
            return False
        return True

    def mtime(self, path):
        """文件修改时间，取不到返回 None。"""
        try:
            return os.stat(path).st_mtime
        except OSError:
            return None
