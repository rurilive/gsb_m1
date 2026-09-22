"""解压编排：把条目录成目标目录下的一棵树，出统计报告。

落点规则（与对拍基准 unseal.reference.SafePlanner 逐条一致，但本模块
不依赖 reference）：

- 条目名含反斜杠、以斜杠开头、有 .. 段、切完为空，整条拒掉
- 条目名按 NFC + casefold 归一，某个前缀被别的拼写占过，整条拒掉
- 落点跟着本包已落下的软链解析，解析结果不许越出目标目录
- 软链目标相对链接所在目录解析，出界拒；硬链目标按归档根相对解析，
  且必须指向本包先落下的普通文件
- 声明尺寸超上限、载荷与声明不符，整条拒掉；拒掉的条目不留痕迹
- 上次 run 留下的完整文件跳过，半截文件重写
"""

import os
import unicodedata

from .entries import (
    KIND_DIR,
    KIND_FILE,
    KIND_HARDLINK,
    KIND_SYMLINK,
    iter_archive,
)

DEFAULT_MAX_ENTRY_BYTES = 256 * 1024 * 1024
CHUNK = 1 << 16

_KNOWN_KINDS = (KIND_FILE, KIND_DIR, KIND_SYMLINK, KIND_HARDLINK)

_TMP_SUFFIX = ".unseal-part"


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
        landing = _Landing(self.dest, self.max_entry_bytes, self.chunk_size)
        for entry in self.entry_source(archive):
            report.add(landing.extract(entry))
        return report


def _split_name(name):
    """名字切段：返回 (段元组, 拒绝理由)。"""
    if "\\" in name:
        return None, "backslash-name"
    if name.startswith("/"):
        return None, "absolute-name"
    parts = tuple(part for part in name.split("/") if part not in ("", "."))
    if not parts:
        return None, "empty-name"
    if ".." in parts:
        return None, "parent-component"
    return parts, None


def _canon(parts):
    return tuple(unicodedata.normalize("NFC", part).casefold()
                 for part in parts)


def _relpath(parts):
    return "/".join(parts)


def _link_target(link_dir, linkname):
    """软链目标相对链接所在目录解析，出界返回 None。"""
    if "\\" in linkname or linkname.startswith("/"):
        return None
    stack = list(link_dir)
    for component in linkname.split("/"):
        if component in ("", "."):
            continue
        if component == "..":
            if not stack:
                return None
            stack.pop()
            continue
        stack.append(component)
    return tuple(stack)


class _Node:
    """本次 run 已落下的一个节点：种类加软链目标（解析后的段元组）。"""

    __slots__ = ("kind", "target")

    def __init__(self, kind, target=None):
        self.kind = kind
        self.target = target


class _Landing:
    """一次 run 的落盘状态：已落节点、已占用拼写、已建目录。

    nodes 以解析后的段元组为键，names 以条目名原始段的归一形式为键；
    两者配合，让落点判定只看本次 run 自己建立的事实，不信盘上任何
    来路不明的东西。
    """

    def __init__(self, dest, max_entry_bytes, chunk_size):
        self.dest = dest
        self.max_entry_bytes = max_entry_bytes
        self.chunk_size = chunk_size
        self.nodes = {}
        self.names = {}
        self.ensured = set()

    def extract(self, entry):
        parts, reason = _split_name(entry.name)
        if reason:
            return self._reject(entry, reason)
        if entry.kind not in _KNOWN_KINDS:
            return self._reject(entry, "unknown-kind")
        if self._collides(parts):
            return self._reject(entry, "case-collision")
        resolved = self._resolve(parts)
        if entry.kind == KIND_DIR:
            return self._mkdir(entry, parts, resolved)
        if entry.kind == KIND_FILE:
            return self._write(entry, parts, resolved)
        if entry.kind == KIND_SYMLINK:
            return self._symlink(entry, parts, resolved)
        return self._hardlink(entry, parts, resolved)

    def _reject(self, entry, reason):
        return EntryResult(entry.name, "reject", None, reason=reason)

    def _disk_path(self, parts):
        return os.path.join(self.dest, *parts)

    def _collides(self, parts):
        """名字的某个前缀归一点已被别的拼写占了，就是大小写碰撞。"""
        for index in range(1, len(parts) + 1):
            seen = self.names.get(_canon(parts[:index]))
            if seen is not None and seen != parts[:index]:
                return True
        return False

    def _resolve(self, parts):
        """跟着已落下的软链解析落点；每个节点只展开一次，绕回就停。"""
        out = []
        pending = list(parts)
        expanded = set()
        while pending:
            component = pending.pop(0)
            key = tuple(out) + (component,)
            node = self.nodes.get(key)
            if node is not None and node.kind == KIND_SYMLINK \
                    and key not in expanded:
                expanded.add(key)
                pending[:0] = list(node.target)
                continue
            out.append(component)
        return tuple(out)

    def _prefix_conflict(self, resolved):
        for index in range(1, len(resolved)):
            node = self.nodes.get(resolved[:index])
            if node is not None and node.kind != KIND_DIR:
                return True
        return False

    def _register(self, parts, resolved, kind, target=None):
        for index in range(1, len(resolved) + 1):
            prefix = resolved[:index]
            node = self.nodes.get(prefix)
            if node is None:
                self.nodes[prefix] = _Node(
                    KIND_DIR if index < len(resolved) else kind,
                    target if index == len(resolved) else None)
            elif index == len(resolved):
                node.kind = kind
                node.target = target
        for index in range(1, len(parts) + 1):
            prefix = parts[:index]
            self.names.setdefault(_canon(prefix), prefix)

    def _ensure_dir(self, parts):
        if not parts or parts in self.ensured:
            return
        path = self._disk_path(parts)
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as exc:
            raise ExtractError("建目录失败 %r: %s" % (path, exc))
        for index in range(1, len(parts) + 1):
            self.ensured.add(parts[:index])

    def _mkdir(self, entry, parts, resolved):
        if self._prefix_conflict(resolved):
            return self._reject(entry, "conflicting-entry")
        node = self.nodes.get(resolved)
        if node is not None and node.kind != KIND_DIR:
            return self._reject(entry, "conflicting-entry")
        self._ensure_dir(resolved)
        self._register(parts, resolved, KIND_DIR)
        return EntryResult(entry.name, "mkdir", _relpath(resolved))

    def _write(self, entry, parts, resolved):
        if self._prefix_conflict(resolved):
            return self._reject(entry, "conflicting-entry")
        node = self.nodes.get(resolved)
        if node is not None and node.kind != KIND_FILE:
            return self._reject(entry, "conflicting-entry")
        if entry.declared_size > self.max_entry_bytes:
            return self._reject(entry, "oversize")
        path = self._disk_path(resolved)
        if node is None and os.path.lexists(path):
            # 上次 run 留下的：完整文件跳过，半截或不认识的重写；
            # 软链和目录不敢动，整条拒掉
            if os.path.islink(path) or os.path.isdir(path):
                return self._reject(entry, "conflicting-entry")
            if os.path.getsize(path) == entry.declared_size:
                self._register(parts, resolved, KIND_FILE)
                return EntryResult(entry.name, "skip", _relpath(resolved))
        size = self._copy_payload(entry, path, resolved)
        if size is None:
            return self._reject(entry, "size-mismatch")
        self._register(parts, resolved, KIND_FILE)
        return EntryResult(entry.name, "write", _relpath(resolved), size=size)

    def _copy_payload(self, entry, path, resolved):
        """载荷先落目标根下的临时文件，尺寸对上声明才建目录换名到位。

        临时文件落在 dest 根部而不是目标旁边：验证通过之前不在目标
        路径上建任何目录，拒掉的条目才真的不留痕迹。
        """
        tmp = self._tmp_path(path)
        total = 0
        try:
            stream = entry.open()
            try:
                flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
                flags |= getattr(os, "O_NOFOLLOW", 0)
                with os.fdopen(os.open(tmp, flags, 0o666), "wb") as out:
                    while total <= entry.declared_size:
                        chunk = stream.read(self.chunk_size)
                        if not chunk:
                            break
                        out.write(chunk)
                        total += len(chunk)
            finally:
                stream.close()
        except Exception:
            self._quiet_unlink(tmp)
            return None
        if total != entry.declared_size:
            self._quiet_unlink(tmp)
            return None
        try:
            self._ensure_dir(resolved[:-1])
        except Exception:
            self._quiet_unlink(tmp)
            raise
        os.replace(tmp, path)
        return total

    def _tmp_path(self, target_path):
        """临时文件路径：避开已落节点和本次目标，防止撞名覆盖。"""
        stem = _TMP_SUFFIX
        while True:
            key = (stem,)
            candidate = os.path.join(self.dest, stem)
            if key not in self.nodes and _canon(key) not in self.names \
                    and candidate != target_path:
                return candidate
            stem += "x"

    def _symlink(self, entry, parts, resolved):
        if self._prefix_conflict(resolved):
            return self._reject(entry, "conflicting-entry")
        if resolved in self.nodes:
            return self._reject(entry, "conflicting-entry")
        target = _link_target(resolved[:-1], entry.linkname)
        if target is None:
            return self._reject(entry, "link-escape")
        path = self._disk_path(resolved)
        if os.path.lexists(path):
            # 上次 run 落过的同一条链才算数，别的来路一律拒
            if os.path.islink(path) and os.readlink(path) == entry.linkname:
                self._register(parts, resolved, KIND_SYMLINK, target)
                return EntryResult(entry.name, "skip", _relpath(resolved))
            return self._reject(entry, "conflicting-entry")
        self._ensure_dir(resolved[:-1])
        os.symlink(entry.linkname, path)
        self._register(parts, resolved, KIND_SYMLINK, target)
        return EntryResult(entry.name, "symlink", _relpath(resolved))

    def _hardlink(self, entry, parts, resolved):
        if self._prefix_conflict(resolved):
            return self._reject(entry, "conflicting-entry")
        if resolved in self.nodes:
            return self._reject(entry, "conflicting-entry")
        linkname, reason = _split_name(entry.linkname)
        if reason:
            return self._reject(entry, "link-escape")
        source = self._resolve(linkname)
        node = self.nodes.get(source)
        if node is None or node.kind != KIND_FILE:
            return self._reject(entry, "missing-link-target")
        path = self._disk_path(resolved)
        if os.path.lexists(path):
            if not os.path.islink(path) \
                    and os.path.samefile(path, self._disk_path(source)):
                self._register(parts, resolved, KIND_FILE)
                return EntryResult(entry.name, "skip", _relpath(resolved))
            return self._reject(entry, "conflicting-entry")
        self._ensure_dir(resolved[:-1])
        os.link(self._disk_path(source), path)
        self._register(parts, resolved, KIND_FILE)
        return EntryResult(entry.name, "hardlink", _relpath(resolved))

    @staticmethod
    def _quiet_unlink(path):
        try:
            os.unlink(path)
        except OSError:
            pass
