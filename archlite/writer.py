"""写侧：条目校验 + 头部拼装 + 拼字节/落盘。

错误口径（对外类型与文案逐字锁定，见 tests/test_archlite.py）：
- 条目类型错误：TypeError
- 条目内容校验（空名 / 含 NUL / 超长）：ValueError
"""

from archlite.entry import ArchiveEntry
from archlite.header import BLOCK_SIZE, END_OF_ARCHIVE, NAME_SIZE, build_header


def _check_entry(e):
    if not isinstance(e, ArchiveEntry):
        raise TypeError("expected ArchiveEntry, got %s" % type(e).__name__)
    if e.name == "":
        raise ValueError("entry name must not be empty")
    if "\x00" in e.name:
        raise ValueError("entry name must not contain NUL")
    nb = e.name.encode("utf-8")
    if len(nb) > NAME_SIZE:
        raise ValueError("entry name too long: %d > 64 bytes" % len(nb))
    return nb


def _entry_chunks(entry):
    """一个条目对应的字节序列：头 + 数据 + 补零。"""
    name_bytes = _check_entry(entry)
    yield build_header(name_bytes, len(entry.data))
    yield entry.data
    yield b"\x00" * ((-len(entry.data)) % BLOCK_SIZE)


def pack_bytes(entries):
    out = bytearray()
    for e in entries:
        for chunk in _entry_chunks(e):
            out += chunk
    out += END_OF_ARCHIVE
    return bytes(out)


def write_archive(path, entries):
    with open(path, "wb") as f:
        for e in entries:
            for chunk in _entry_chunks(e):
                f.write(chunk)
        f.write(END_OF_ARCHIVE)
