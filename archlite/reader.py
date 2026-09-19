"""读侧：从字节串或文件扫描条目（只读，不校验写侧规则）。

错误口径（对外类型与文案逐字锁定，见 tests/test_archlite.py）：
- 输入类型错误：TypeError
- 归档格式错误（魔数 / 校验和 / 截断）：ValueError
- find_entry 捕获 ValueError 一律返回 None（恢复工具依赖的历史行为）
"""

import io

from archlite.entry import ArchiveEntry
from archlite.header import BLOCK_SIZE, ZERO_BLOCK, parse_header


def _scan_entries(read, reject_short_first_block):
    """用 read(n) 逐块扫描；不足一块的尾部字节与结束块之后的字节一律忽略。"""
    entries = []
    index = 0
    first = True
    while True:
        block = read(BLOCK_SIZE)
        if len(block) < BLOCK_SIZE:
            if first and reject_short_first_block:
                raise ValueError("truncated header: got %d bytes" % len(block))
            break
        first = False
        if block == ZERO_BLOCK:
            break
        name, size = parse_header(block, index)
        body = read(size)
        if len(body) < size:
            raise ValueError(
                "truncated data for %r: expected %d bytes, got %d" % (name, size, len(body))
            )
        entries.append(ArchiveEntry(name, body))
        padding = (-size) % BLOCK_SIZE
        if padding:
            read(padding)
        index += 1
    return entries


def unpack_bytes(blob):
    if not isinstance(blob, (bytes, bytearray)):
        raise TypeError("expected bytes")
    return _scan_entries(io.BytesIO(bytes(blob)).read, reject_short_first_block=True)


def read_archive(path):
    with open(path, "rb") as f:
        return _scan_entries(f.read, reject_short_first_block=False)


def find_entry(blob, name):
    try:
        entries = unpack_bytes(blob)
    except ValueError:
        return None
    for e in entries:
        if e.name == name:
            return e
    return None
