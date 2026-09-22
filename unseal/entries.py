"""归档条目的统一视图：zip 与 tar 都归一成 Entry 序列。"""

import stat
import tarfile
import zipfile

KIND_FILE = "file"
KIND_DIR = "dir"
KIND_SYMLINK = "symlink"
KIND_HARDLINK = "hardlink"
KIND_OTHER = "other"


class ArchiveError(Exception):
    """归档本身读不出来，或者里面的东西解不了。"""


class _Handle:
    """一次迭代共用的归档句柄：谁先要谁把底层归档建出来。

    条目可能被攒下来慢慢读，句柄跟着条目走，最后一个引用掉光的时候
    由 GC 收尾。
    """

    def __init__(self, opener):
        self._opener = opener
        self._handle = None

    def get(self):
        if self._handle is None:
            self._handle = self._opener()
        return self._handle

    def close(self):
        handle, self._handle = self._handle, None
        if handle is not None:
            try:
                handle.close()
            except Exception:
                pass

    def __del__(self):
        self.close()


class Entry:
    """归一后的一个归档条目。

    name 是归档里原样的名字，一个字节都不动；declared_size 是头部里
    声明的解压尺寸；linkname 是软链指向或硬链接的目标；kind 是四个
    已知种类之一，别的类型归到 KIND_OTHER。open() 给只读二进制流，
    要趁外层迭代还没走完的时候读。
    """

    __slots__ = ("name", "kind", "declared_size", "linkname", "mode", "_opener")

    def __init__(self, name, kind, declared_size=0, linkname="", mode=0o644,
                 opener=None):
        self.name = name
        self.kind = kind
        self.declared_size = declared_size
        self.linkname = linkname
        self.mode = mode
        self._opener = opener

    def open(self):
        if self._opener is None:
            raise ArchiveError("条目 %r 没有可读的载荷" % self.name)
        return self._opener()

    def __repr__(self):
        return "Entry(%r, %s, declared=%d)" % (self.name, self.kind,
                                               self.declared_size)


def _zip_kind(info):
    """zip 条目靠高位的 unix 权限位判种类，没带权限位的当普通文件。"""
    mode = (info.external_attr >> 16) & 0xFFFF
    if info.is_dir() or stat.S_ISDIR(mode):
        return KIND_DIR, mode
    if stat.S_ISLNK(mode):
        return KIND_SYMLINK, mode
    return KIND_FILE, mode


def iter_zip(path):
    """zip 归档的条目序列，按中央目录的顺序。"""
    handle = _Handle(lambda: zipfile.ZipFile(path))
    archive = handle.get()
    for info in archive.infolist():
        kind, mode = _zip_kind(info)
        if kind == KIND_DIR:
            yield Entry(info.filename, KIND_DIR, 0, mode=mode or 0o755)
        elif kind == KIND_SYMLINK:
            linkname = archive.read(info).decode("utf-8", "surrogateescape")
            yield Entry(info.filename, KIND_SYMLINK, 0, linkname,
                        mode or 0o777)
        else:
            yield Entry(info.filename, KIND_FILE, info.file_size,
                        mode=mode or 0o644,
                        opener=lambda info=info: handle.get().open(info))


def _tar_kind(member):
    if member.isdir():
        return KIND_DIR
    if member.issym():
        return KIND_SYMLINK
    if member.islnk():
        return KIND_HARDLINK
    if member.isfile():
        return KIND_FILE
    return KIND_OTHER


def iter_tar(path):
    """tar 归档的条目序列。"""
    handle = _Handle(lambda: tarfile.open(path, mode="r:*"))
    archive = handle.get()
    for member in archive:
        kind = _tar_kind(member)
        if kind == KIND_FILE:
            yield Entry(member.name, KIND_FILE, member.size,
                        mode=member.mode,
                        opener=lambda member=member: handle.get().extractfile(member))
        elif kind == KIND_SYMLINK:
            yield Entry(member.name, KIND_SYMLINK, 0, member.linkname,
                        member.mode)
        elif kind == KIND_HARDLINK:
            yield Entry(member.name, KIND_HARDLINK, 0, member.linkname,
                        member.mode)
        elif kind == KIND_DIR:
            yield Entry(member.name, KIND_DIR, 0, mode=member.mode)
        else:
            yield Entry(member.name, KIND_OTHER, 0, mode=member.mode)


def iter_archive(path):
    """按内容嗅探格式，返回条目序列。认不出来就抛 ArchiveError。"""
    with open(path, "rb") as handle:
        head = handle.read(4)
    if head[:2] == b"PK":
        return iter_zip(path)
    if tarfile.is_tarfile(path):
        return iter_tar(path)
    raise ArchiveError("不认识的归档格式: %s" % path)
