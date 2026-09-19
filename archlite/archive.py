"""archlite: 内部备份工具用的 tar-lite 归档格式（512 字节块，无压缩，纯标准库）。

格式：每个条目 = 512 字节头 + 数据（补零到 512 的倍数），归档以两个全零块结尾。
头部布局：0-4 魔数 "ARCL"；4-68 名字（utf-8，NUL 补齐）；68-76 数据长度（大端 u64）；
76-80 校验和（大端 u32，对校验和字段置零后的整个头部按字节求和）；80-512 全零填充。

行为口径（历史形成的，全部要保住，tests/test_archlite.py 是清单）：
- 归档头部不足 512 字节报错；归档中部/尾部不足一块的字节与结束块之后的字节一律忽略
- find_entry 扫描时遇到坏归档不抛错，返回 None（恢复工具依赖）
- 打包输出字节级确定（无时间戳等易变字段）
"""

import struct

MAGIC = b"ARCL"


class ArchiveEntry(object):
    """归档里的一个条目。"""

    def __init__(self, name, data):
        if not isinstance(name, str):
            raise TypeError("entry name must be str")
        if not isinstance(data, bytes):
            raise TypeError("entry data must be bytes")
        self.name = name
        self.data = data

    def __eq__(self, other):
        if not isinstance(other, ArchiveEntry):
            return NotImplemented
        return self.name == other.name and self.data == other.data

    def __repr__(self):
        return "ArchiveEntry(name=%r, data=%d bytes)" % (self.name, len(self.data))


def _check_entry(e):
    if not isinstance(e, ArchiveEntry):
        raise TypeError("expected ArchiveEntry, got %s" % type(e).__name__)
    if e.name == "":
        raise ValueError("entry name must not be empty")
    if "\x00" in e.name:
        raise ValueError("entry name must not contain NUL")
    nb = e.name.encode("utf-8")
    if len(nb) > 64:
        raise ValueError("entry name too long: %d > 64 bytes" % len(nb))
    return nb


def pack_bytes(entries):
    out = bytearray()
    for e in entries:
        nb = _check_entry(e)
        head = bytearray(512)
        head[0:4] = MAGIC
        head[4:4 + len(nb)] = nb
        head[68:76] = struct.pack(">Q", len(e.data))
        chk = sum(head) & 0xFFFFFFFF
        head[76:80] = struct.pack(">I", chk)
        out += head
        out += e.data
        out += b"\x00" * ((-len(e.data)) % 512)
    out += b"\x00" * 1024
    return bytes(out)


def unpack_bytes(blob):
    if not isinstance(blob, (bytes, bytearray)):
        raise TypeError("expected bytes")
    blob = bytes(blob)
    if len(blob) < 512:
        raise ValueError("truncated header: got %d bytes" % len(blob))
    entries = []
    off = 0
    idx = 0
    while True:
        blk = blob[off:off + 512]
        if len(blk) < 512:
            break
        if blk == b"\x00" * 512:
            break
        if blk[:4] != MAGIC:
            raise ValueError("not an archlite archive: magic=%r" % bytes(blk[:4]))
        stored = struct.unpack(">I", blk[76:80])[0]
        calc = (sum(blk[:76]) + sum(blk[80:])) & 0xFFFFFFFF
        if calc != stored:
            raise ValueError("header checksum mismatch at entry %d" % idx)
        raw = blk[4:68].split(b"\x00", 1)[0]
        name = raw.decode("utf-8")
        size = struct.unpack(">Q", blk[68:76])[0]
        body = blob[off + 512:off + 512 + size]
        if len(body) < size:
            raise ValueError(
                "truncated data for %r: expected %d bytes, got %d" % (name, size, len(body))
            )
        entries.append(ArchiveEntry(name, body))
        off = off + 512 + ((size + 511) // 512) * 512
        idx += 1
        if off >= len(blob):
            break
    return entries


def find_entry(blob, name):
    try:
        entries = unpack_bytes(blob)
    except ValueError:
        return None
    for e in entries:
        if e.name == name:
            return e
    return None


def write_archive(path, entries):
    with open(path, "wb") as f:
        for e in entries:
            nb = _check_entry(e)
            head = bytearray(512)
            head[0:4] = MAGIC
            head[4:4 + len(nb)] = nb
            head[68:76] = struct.pack(">Q", len(e.data))
            chk = sum(head) & 0xFFFFFFFF
            head[76:80] = struct.pack(">I", chk)
            f.write(bytes(head))
            f.write(e.data)
            f.write(b"\x00" * ((-len(e.data)) % 512))
        f.write(b"\x00" * 1024)


def read_archive(path):
    entries = []
    with open(path, "rb") as f:
        idx = 0
        while True:
            blk = f.read(512)
            if len(blk) < 512:
                break
            if blk == b"\x00" * 512:
                break
            if blk[:4] != MAGIC:
                raise ValueError("not an archlite archive: magic=%r" % bytes(blk[:4]))
            stored = struct.unpack(">I", blk[76:80])[0]
            calc = (sum(blk[:76]) + sum(blk[80:])) & 0xFFFFFFFF
            if calc != stored:
                raise ValueError("header checksum mismatch at entry %d" % idx)
            raw = blk[4:68].split(b"\x00", 1)[0]
            name = raw.decode("utf-8")
            size = struct.unpack(">Q", blk[68:76])[0]
            body = f.read(size)
            if len(body) < size:
                raise ValueError(
                    "truncated data for %r: expected %d bytes, got %d" % (name, size, len(body))
                )
            entries.append(ArchiveEntry(name, body))
            pad = (-size) % 512
            if pad:
                f.read(pad)
            idx += 1
    return entries
