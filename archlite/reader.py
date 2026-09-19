"""reader 层：archlite 字节流 -> ArchiveEntry。

头部解析（魔数/校验和/字段）只在 parse_header 里做一次；
unpack_bytes（内存）与 read_archive（文件）共用同一个块扫描循环。

错误口径（文案逐字锁定，见 tests/test_archlite.py）：
- 入参类型不对：TypeError
- 归档畸形（首块截断/魔数错/校验和错/数据截断）：ValueError，固定文案
- 名字非 utf-8：UnicodeDecodeError（ValueError 子类，find_entry 视同坏归档）
- 文件层面错误（如 FileNotFoundError）不在本层吞，原样向上抛
"""

import io
import struct

from archlite import format as fmt
from archlite.entry import ArchiveEntry

_ZERO_BLOCK = b"\x00" * fmt.BLOCK_SIZE


def parse_header(block, index):
    """校验并解析一个 512 字节头，返回 (name, data_size)。

    检查顺序：魔数 -> 校验和 -> 名字解码 -> 长度。
    """
    if block[:fmt.MAGIC_SIZE] != fmt.MAGIC:
        raise ValueError("not an archlite archive: magic=%r" % bytes(block[:fmt.MAGIC_SIZE]))
    stored_checksum = struct.unpack(
        fmt.CHECKSUM_FORMAT,
        block[fmt.CHECKSUM_OFFSET:fmt.CHECKSUM_OFFSET + fmt.CHECKSUM_SIZE],
    )[0]
    if fmt.header_checksum(block) != stored_checksum:
        raise ValueError("header checksum mismatch at entry %d" % index)
    name_end = fmt.NAME_OFFSET + fmt.NAME_SIZE
    raw_name = block[fmt.NAME_OFFSET:name_end].split(b"\x00", 1)[0]
    name = raw_name.decode("utf-8")
    size = struct.unpack(
        fmt.SIZE_FORMAT, block[fmt.SIZE_OFFSET:fmt.SIZE_OFFSET + fmt.SIZE_SIZE]
    )[0]
    return name, size


def _read_stream(stream, require_full_first_block):
    """扫描一个 read(n) 字节流，返回条目列表。

    require_full_first_block=True 时首块不足 512 报 truncated header
    （unpack_bytes 口径）；否则安静结束（read_archive 空文件口径）。
    中部/尾部不足一块的字节与结束块之后的字节一律忽略。
    """
    entries = []
    index = 0
    while True:
        block = stream.read(fmt.BLOCK_SIZE)
        if len(block) < fmt.BLOCK_SIZE:
            if require_full_first_block and index == 0:
                raise ValueError("truncated header: got %d bytes" % len(block))
            break
        if block == _ZERO_BLOCK:
            break
        name, size = parse_header(block, index)
        body = stream.read(size)
        if len(body) < size:
            raise ValueError(
                "truncated data for %r: expected %d bytes, got %d"
                % (name, size, len(body))
            )
        entries.append(ArchiveEntry(name, body))
        padding = fmt.pad_length(size)
        if padding:
            stream.read(padding)
        index += 1
    return entries


def unpack_bytes(blob):
    """从完整归档字节解出条目列表。"""
    if not isinstance(blob, (bytes, bytearray)):
        raise TypeError("expected bytes")
    return _read_stream(io.BytesIO(blob), require_full_first_block=True)


def read_archive(path):
    """从 path（rb）流式解出条目列表；文件层错误原样上抛。"""
    with open(path, "rb") as f:
        return _read_stream(f, require_full_first_block=False)


def find_entry(blob, name):
    """按名字找第一个同名条目；找不到或归档损坏一律返回 None（历史行为）。"""
    try:
        entries = unpack_bytes(blob)
    except ValueError:
        return None
    for entry in entries:
        if entry.name == name:
            return entry
    return None
