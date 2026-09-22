"""对拍基准与构造工具，审计时用来复现和判定，线上路径不许依赖本模块。

SafePlanner 只推演不落盘：按条目顺序走一遍，给出每条该走什么动作、
该落到哪个相对路径、还是整条拒掉。带载荷的条目会把流真读掉，长度和
声明对不上就按 size-mismatch 拒。判定规则：

- 名字先切段：含反斜杠、以斜杠开头、有 .. 段、切完为空，直接拒；
  空段和 . 段丢掉
- 条目名按 NFC 加 casefold 归一，某个前缀的归一点已经被别的拼写
  占了，后到的拒（大小写不敏感文件系统上会互相盖）；这段只看名字
  本身，不比跟完软链的落点
- 落点要跟着已建立的软链解析，解析结果不许越出目标目录；拒掉的
  条目不留痕迹，连中间目录也不留
- 目录与普通文件可以原地重复（后到的盖前一个）；路径中间那一段
  已经是普通文件或软链，或者终点要盖掉不同种类的节点，拒
- 软链的目标相对链接所在目录解析，出界就拒；硬链接的目标按归档
  根相对解析，指向的文件必须在这包里先出现过，写错的链接名按出界拒
- 普通文件声明的尺寸超过上限拒；载荷长度与声明不符也拒

动作码：write mkdir symlink hardlink reject
理由码：absolute-name parent-component backslash-name empty-name
        unknown-kind case-collision link-escape conflicting-entry
        missing-link-target oversize size-mismatch

forge_zip / forge_tar 用来手工拼归档：名字一个字节不改地写进去，
软链、硬链、目录、谎报尺寸都能造；zip 的尺寸谎报会连本地头和中央
目录一起改。tar 的头里没法写假尺寸（写进去读出来就错位），要造
尺寸不符就用 zip，或者自己拼 Entry 喂给两边。
"""

import io
import os
import stat
import struct
import tarfile
import unicodedata
import warnings
import zipfile
from dataclasses import dataclass

from .entries import (
    KIND_DIR,
    KIND_FILE,
    KIND_HARDLINK,
    KIND_SYMLINK,
    iter_archive,
)
from .extract import DEFAULT_MAX_ENTRY_BYTES

PAYLOAD_CHUNK = 1 << 16


class Verdict:
    """一条的判定：动作、落点（相对目标目录的 posix 路径）、拒绝理由。"""

    __slots__ = ("name", "action", "relpath", "reason")

    def __init__(self, name, action, relpath=None, reason=None):
        self.name = name
        self.action = action
        self.relpath = relpath
        self.reason = reason

    def __repr__(self):
        return "Verdict(%r, %s, %r, reason=%r)" % (self.name, self.action,
                                                   self.relpath, self.reason)


class _Node:
    __slots__ = ("raw", "kind", "target")

    def __init__(self, raw, kind, target=None):
        self.raw = raw
        self.kind = kind
        self.target = target


def _canon(parts):
    return tuple(unicodedata.normalize("NFC", part).casefold()
                 for part in parts)


def _relpath(parts):
    return "/".join(parts)


class SafePlanner:
    """安全解压的判定基准。"""

    def __init__(self, dest, max_entry_bytes=DEFAULT_MAX_ENTRY_BYTES):
        self.dest = os.path.abspath(dest)
        self.max_entry_bytes = max_entry_bytes
        self.nodes = {}
        self.names = {}

    def run(self, archive, entry_source=iter_archive):
        return self.plan(entry_source(archive))

    def plan(self, entries):
        return [self.decide(entry) for entry in entries]

    def decide(self, entry):
        parts, reason = _split(entry.name)
        if reason:
            return self._reject(entry, reason)
        if entry.kind not in (KIND_FILE, KIND_DIR, KIND_SYMLINK, KIND_HARDLINK):
            return self._reject(entry, "unknown-kind")
        if self._collides(parts):
            return self._reject(entry, "case-collision")
        resolved = self._resolve(parts)
        if resolved is None:
            return self._reject(entry, "link-escape")
        if entry.kind == KIND_DIR:
            if self._prefix_conflict(resolved):
                return self._reject(entry, "conflicting-entry")
            node = self.nodes.get(resolved)
            if node is not None and node.kind != KIND_DIR:
                return self._reject(entry, "conflicting-entry")
            self._register(parts, resolved, KIND_DIR)
            return Verdict(entry.name, "mkdir", _relpath(resolved))
        if entry.kind == KIND_FILE:
            if self._prefix_conflict(resolved):
                return self._reject(entry, "conflicting-entry")
            node = self.nodes.get(resolved)
            if node is not None and node.kind != KIND_FILE:
                return self._reject(entry, "conflicting-entry")
            if entry.declared_size > self.max_entry_bytes:
                return self._reject(entry, "oversize")
            if not self._payload_matches(entry):
                return self._reject(entry, "size-mismatch")
            self._register(parts, resolved, KIND_FILE)
            return Verdict(entry.name, "write", _relpath(resolved))
        if entry.kind == KIND_SYMLINK:
            if self._prefix_conflict(resolved):
                return self._reject(entry, "conflicting-entry")
            if resolved in self.nodes:
                return self._reject(entry, "conflicting-entry")
            target = self._link_target(resolved[:-1], entry.linkname)
            if target is None:
                return self._reject(entry, "link-escape")
            self._register(parts, resolved, KIND_SYMLINK, target)
            return Verdict(entry.name, "symlink", _relpath(resolved))
        if entry.kind == KIND_HARDLINK:
            if self._prefix_conflict(resolved):
                return self._reject(entry, "conflicting-entry")
            if resolved in self.nodes:
                return self._reject(entry, "conflicting-entry")
            linkname, reason = _split(entry.linkname)
            if reason:
                return self._reject(entry, "link-escape")
            target = self._resolve(linkname)
            if target is None:
                return self._reject(entry, "link-escape")
            source = self.nodes.get(target)
            if source is None or source.kind != KIND_FILE:
                return self._reject(entry, "missing-link-target")
            self._register(parts, resolved, KIND_FILE)
            return Verdict(entry.name, "hardlink", _relpath(resolved))
        return self._reject(entry, "unknown-kind")

    def _reject(self, entry, reason):
        return Verdict(entry.name, "reject", reason=reason)

    def _prefix_conflict(self, resolved):
        for index in range(1, len(resolved)):
            node = self.nodes.get(resolved[:index])
            if node is not None and node.kind != KIND_DIR:
                return True
        return False

    def _collides(self, parts):
        """名字的某个前缀归一点已被别的拼写占了，就是大小写碰撞。

        只看条目名本身，不看跟完软链的落点：不敏感文件系统上撞的就是
        这两串拼写。
        """
        for index in range(1, len(parts) + 1):
            seen = self.names.get(_canon(parts[:index]))
            if seen is not None and seen != parts[:index]:
                return True
        return False

    def _resolve(self, parts):
        """跟着已注册的软链解析落点，出界返回 None。

        跟软链的时候每个节点只展开一次，再绕回来就当普通名字停下，
        跟盘上 realpath 撞上自环时的脾气一致。
        """
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

    def _link_target(self, link_dir, linkname):
        """软链自己的目标：相对链接所在目录解析，出界返回 None。"""
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

    def _payload_matches(self, entry):
        try:
            stream = entry.open()
            total = 0
            try:
                while True:
                    chunk = stream.read(PAYLOAD_CHUNK)
                    if not chunk:
                        break
                    total += len(chunk)
            finally:
                stream.close()
        except Exception:
            return False
        return total == entry.declared_size

    def _register(self, parts, resolved, kind, target=None):
        for index in range(1, len(resolved) + 1):
            prefix = resolved[:index]
            node = self.nodes.get(prefix)
            if node is None:
                self.nodes[prefix] = _Node(
                    prefix, KIND_DIR if index < len(resolved) else kind,
                    target if index == len(resolved) else None)
            elif index == len(resolved):
                node.raw = prefix
                node.kind = kind
                node.target = target
        for index in range(1, len(parts) + 1):
            prefix = parts[:index]
            self.names.setdefault(_canon(prefix), prefix)


def _split(name):
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


@dataclass
class Forged:
    """要拼进归档的一条。kind 取 file / dir / symlink / hardlink。"""

    name: str
    kind: str = KIND_FILE
    data: bytes = b""
    target: str = ""
    declared: int = None


def forge_zip(path, items):
    """按给定条目拼一个 zip；declared 用来谎报普通文件的解压尺寸。

    同名条目是合法归档里也可能有的东西，拼的时候别让 zipfile 唠叨。
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _write_zip(path, items)
    patches = {index: item.declared for index, item in enumerate(items)
               if item.kind == KIND_FILE and item.declared is not None
               and item.declared != len(item.data)}
    if patches:
        _patch_zip_sizes(path, patches)


def _write_zip(path, items):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for item in items:
            info = zipfile.ZipInfo(item.name)
            info.create_system = 3
            if item.kind == KIND_DIR:
                info.external_attr = (stat.S_IFDIR | 0o755) << 16
                archive.writestr(info, b"")
            elif item.kind == KIND_SYMLINK:
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(info, item.target.encode("utf-8"))
            elif item.kind == KIND_FILE:
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                archive.writestr(info, item.data)
            else:
                raise ValueError("zip 里拼不出 %r" % item.kind)


def _patch_zip_sizes(path, patches):
    """把本地头和中央目录里的解压尺寸改成谎报值。"""
    with open(path, "rb") as handle:
        raw = bytearray(handle.read())
    with zipfile.ZipFile(path) as archive:
        start = archive.start_dir
        infos = archive.infolist()
    position = start
    for index, info in enumerate(infos):
        name_len, extra_len, comment_len = struct.unpack_from("<HHH", raw,
                                                              position + 28)
        declared = patches.get(index)
        if declared is not None:
            struct.pack_into("<I", raw, position + 24, declared)
            struct.pack_into("<I", raw, info.header_offset + 22, declared)
        position += 46 + name_len + extra_len + comment_len
        if declared is not None and not 0 <= declared <= 0xFFFFFFFF:
            raise ValueError("zip 头里的尺寸塞不下 %r" % declared)
    with open(path, "wb") as handle:
        handle.write(bytes(raw))


def forge_tar(path, items):
    """按给定条目拼一个 tar；tar 头里尺寸写不了假，谎报尺寸请走 zip。"""
    with tarfile.open(path, "w") as archive:
        for item in items:
            info = tarfile.TarInfo(item.name)
            if item.kind == KIND_DIR:
                info.type = tarfile.DIRTYPE
                info.mode = 0o755
                archive.addfile(info)
            elif item.kind == KIND_SYMLINK:
                info.type = tarfile.SYMTYPE
                info.linkname = item.target
                archive.addfile(info)
            elif item.kind == KIND_HARDLINK:
                info.type = tarfile.LNKTYPE
                info.linkname = item.target
                archive.addfile(info)
            elif item.kind == KIND_FILE:
                if item.declared not in (None, len(item.data)):
                    raise ValueError("tar 头里的尺寸写不了假")
                info.size = len(item.data)
                info.mode = 0o644
                archive.addfile(info, io.BytesIO(item.data))
            else:
                raise ValueError("tar 里拼不出 %r" % item.kind)
