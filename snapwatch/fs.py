"""文件系统访问的薄封装：扫描器只从这里碰 os，测试可以换成自己的实现。"""

import os
import stat as stat_module


class StatEntry:
    """一次 stat 拿到的元数据。"""

    __slots__ = ("mtime_ns", "size", "inode", "is_dir")

    def __init__(self, mtime_ns, size, inode, is_dir):
        self.mtime_ns, self.size = mtime_ns, size
        self.inode, self.is_dir = inode, is_dir

    def __eq__(self, other):
        return (self.mtime_ns, self.size, self.inode, self.is_dir) == (
            other.mtime_ns, other.size, other.inode, other.is_dir)

    def __repr__(self):
        return "StatEntry(mtime_ns=%r, size=%r, inode=%r, is_dir=%r)" % (
            self.mtime_ns, self.size, self.inode, self.is_dir)


class FileSystem:
    """PollScanner 用到的全部能力，测试继承这个类做替身。"""

    def stat(self, path):
        """路径的元数据，路径不存在时抛 FileNotFoundError。"""
        raise NotImplementedError

    def scandir(self, path):
        """目录下所有名字，升序；目录读不出来时抛 OSError。"""
        raise NotImplementedError

    def read_bytes(self, path):
        """文件内容。"""
        raise NotImplementedError


class SysFS(FileSystem):
    """真实文件系统。"""

    def stat(self, path):
        info = os.stat(path)
        return StatEntry(info.st_mtime_ns, info.st_size, info.st_ino,
                         stat_module.S_ISDIR(info.st_mode))

    def scandir(self, path):
        with os.scandir(path) as entries:
            return sorted(entry.name for entry in entries)

    def read_bytes(self, path):
        with open(path, "rb") as handle:
            return handle.read()
