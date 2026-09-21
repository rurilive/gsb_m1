"""快照扫描：走一遍目录树，把每个节点的元数据和内容摘要记下来。"""

import hashlib
import os

from .fs import SysFS


class Entry:
    """快照里的一个节点，路径是相对 root 的 posix 串。"""

    __slots__ = ("path", "is_dir", "mtime_ns", "size", "inode",
                 "_abs", "_fs", "_digest")

    def __init__(self, path, is_dir, mtime_ns, size, inode,
                 abs_path=None, fs=None, digest=None):
        self.path, self.is_dir = path, is_dir
        self.mtime_ns, self.size = mtime_ns, size
        self.inode, self._abs = inode, abs_path
        self._fs, self._digest = fs, digest

    @property
    def digest(self):
        """文件内容的 sha256；快照里没算过就现读一次，目录恒为 None。"""
        if self.is_dir:
            return None
        if self._digest is None:
            data = self._fs.read_bytes(self._abs)
            self._digest = hashlib.sha256(data).hexdigest()
        return self._digest

    def __repr__(self):
        return "Entry(%r, is_dir=%r, size=%r)" % (
            self.path, self.is_dir, self.size)


class Snapshot:
    """一次扫描的结果。"""

    def __init__(self, root):
        self.root = root
        self.entries = {}

    def entry(self, path):
        """相对路径对应的 Entry，没有这个路径时抛 KeyError。"""
        return self.entries[path]

    def paths(self):
        return sorted(self.entries)

    def __len__(self):
        return len(self.entries)


class PollScanner:
    """把 root 下的目录树扫成 Snapshot。"""

    def __init__(self, fs, root):
        self.fs = fs
        self.root = root

    def _abs(self, rel):
        return os.path.join(self.root, rel) if rel else self.root

    def scan(self):
        snapshot = Snapshot(self.root)
        self._walk("", snapshot)
        return snapshot

    def _walk(self, rel, snapshot):
        try:
            names = self.fs.scandir(self._abs(rel))
        except OSError:
            return
        for name in names:
            child = name if not rel else rel + "/" + name
            try:
                info = self.fs.stat(self._abs(child))
            except OSError:
                continue
            digest = None
            if not info.is_dir:
                content = self.fs.read_bytes(self._abs(child))
                digest = hashlib.sha256(content).hexdigest()
            snapshot.entries[child] = Entry(
                child, info.is_dir, info.mtime_ns, info.size, info.inode,
                abs_path=self._abs(child), fs=self.fs, digest=digest)
            if info.is_dir:
                self._walk(child, snapshot)
