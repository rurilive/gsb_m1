"""writer 层：条目 -> archlite 字节块（内存或文件）。

只负责拼装与写出，头部布局一律取自 archlite.format；不做读取/校验归档。
"""

import struct

from archlite import format as fmt
from archlite.entry import validate_entry


def build_header(name_bytes, data_len):
    """拼装一个 512 字节头（含校验和）。"""
    header = bytearray(fmt.HEADER_SIZE)
    header[fmt.MAGIC_OFFSET:fmt.MAGIC_OFFSET + fmt.MAGIC_SIZE] = fmt.MAGIC
    header[fmt.NAME_OFFSET:fmt.NAME_OFFSET + len(name_bytes)] = name_bytes
    header[fmt.SIZE_OFFSET:fmt.SIZE_OFFSET + fmt.SIZE_SIZE] = struct.pack(
        fmt.SIZE_FORMAT, data_len
    )
    checksum = fmt.header_checksum(header)
    header[fmt.CHECKSUM_OFFSET:fmt.CHECKSUM_OFFSET + fmt.CHECKSUM_SIZE] = struct.pack(
        fmt.CHECKSUM_FORMAT, checksum
    )
    return bytes(header)


def iter_blocks(entries):
    """逐条产出 头块/数据块/补齐块，末尾产出两个全零结束块。"""
    for entry in entries:
        name_bytes = validate_entry(entry)
        yield build_header(name_bytes, len(entry.data))
        yield entry.data
        yield b"\x00" * fmt.pad_length(len(entry.data))
    yield b"\x00" * (fmt.HEADER_SIZE * fmt.END_BLOCKS)


def pack_bytes(entries):
    """把条目打包成完整归档字节。"""
    return b"".join(iter_blocks(entries))


def write_archive(path, entries):
    """把条目打包写入 path（wb）。"""
    with open(path, "wb") as f:
        for block in iter_blocks(entries):
            f.write(block)
