"""解压编排：把条目录成目标目录下的一棵树，出统计报告。"""

import os

from .entries import (
    KIND_DIR,
    KIND_FILE,
    KIND_HARDLINK,
    KIND_SYMLINK,
    iter_archive,
)

DEFAULT_MAX_ENTRY_BYTES = 256 * 1024 * 1024
CHUNK = 1 << 16


class ExtractError(Exception):
    """解压过程中出问题，整次停住。"""


class EntryResult:
    """一个条目的落盘流水。

    name 是归档里原样的名字，action 是 write / mkdir / symlink /
    hardlink / skip / reject，relpath 是相对目标目录的 posix 路径，
    reason 只在 reject 时有值，size 是这次写出去的字节数。
    """

    __slots__ = ("name", "action", "relpath", "reason", "size")

    def __init__(self, name, action, relpath, reason=None, size=0):
        self.name = name
        self.action = action
        self.relpath = relpath
        self.reason = reason
        self.size = size

    def __repr__(self):
        return "EntryResult(%r, %s, %r)" % (self.relpath, self.action,
                                            self.reason)


class ExtractReport:
    """一次解压的结果：逐条流水加汇总。"""

    def __init__(self, archive=None, dest=None):
        self.archive = archive
        self.dest = dest
        self.results = []
        self.bytes = 0

    def add(self, result):
        self.results.append(result)
        self.bytes += result.size
        return result

    def _count(self, *actions):
        return sum(1 for item in self.results if item.action in actions)

    @property
    def written(self):
        return self._count("write")

    @property
    def dirs(self):
        return self._count("mkdir")

    @property
    def links(self):
        return self._count("symlink", "hardlink")

    @property
    def skipped(self):
        return self._count("skip")

    @property
    def rejected(self):
        return self._count("reject")

    def summary(self):
        return ("%d 条：文件 %d，目录 %d，链接 %d，跳过 %d，拒绝 %d，共 %d 字节"
                % (len(self.results), self.written, self.dirs, self.links,
                   self.skipped, self.rejected, self.bytes))

    def __repr__(self):
        return "ExtractReport(%r, %d 条)" % (self.archive, len(self.results))


class Extractor:
    """把归档摊到 dest 下，条目按归档里的相对路径落。

    entry_source 是条目来源，默认 iter_archive，测试里可以换成合成
    条目序列。max_entry_bytes 是单条声明的尺寸上限。
    """

    def __init__(self, dest, max_entry_bytes=DEFAULT_MAX_ENTRY_BYTES,
                 entry_source=iter_archive, chunk_size=CHUNK):
        self.dest = os.path.abspath(dest)
        self.max_entry_bytes = max_entry_bytes
        self.entry_source = entry_source
        self.chunk_size = chunk_size

    def run(self, archive):
        report = ExtractReport(archive, self.dest)
        os.makedirs(self.dest, exist_ok=True)
        for entry in self.entry_source(archive):
            report.add(self._extract(entry))
        return report

    def _extract(self, entry):
        target = os.path.join(self.dest, entry.name)
        if entry.kind == KIND_DIR:
            os.makedirs(target, exist_ok=True)
            return EntryResult(entry.name, "mkdir", entry.name)
        if entry.kind == KIND_SYMLINK:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            os.symlink(entry.linkname, target)
            return EntryResult(entry.name, "symlink", entry.name)
        if entry.kind == KIND_HARDLINK:
            source = os.path.join(self.dest, entry.linkname)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            os.link(source, target)
            return EntryResult(entry.name, "hardlink", entry.name)
        if entry.kind == KIND_FILE:
            if os.path.exists(target):
                return EntryResult(entry.name, "skip", entry.name)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            size = self._copy(entry, target)
            return EntryResult(entry.name, "write", entry.name, size=size)
        raise ExtractError("不认识的条目类型: %r" % entry.kind)

    def _copy(self, entry, target):
        total = 0
        stream = entry.open()
        try:
            with open(target, "wb") as out:
                while True:
                    chunk = stream.read(self.chunk_size)
                    if not chunk:
                        break
                    out.write(chunk)
                    total += len(chunk)
        finally:
            stream.close()
        return total
