"""头部布局常量与编解码：读写两侧唯一的事实来源，加字段只改这里。

布局（512 字节定长头）：
  [0:4)    魔数 MAGIC
  [4:68)   名字（utf-8，NUL 补齐，最长 64 字节）
  [68:76)  数据长度（大端 u64）
  [76:80)  校验和（大端 u32，见 checksum()）
  [80:512) 全零填充
"""

import struct

BLOCK_SIZE = 512
MAGIC = b"ARCL"

NAME_OFFSET = 4
NAME_SIZE = 64
NAME_END = NAME_OFFSET + NAME_SIZE
SIZE_OFFSET = NAME_END
SIZE_END = SIZE_OFFSET + 8
CHECKSUM_OFFSET = SIZE_END
CHECKSUM_END = CHECKSUM_OFFSET + 4

ZERO_BLOCK = b"\x00" * BLOCK_SIZE
END_OF_ARCHIVE = ZERO_BLOCK * 2


def checksum(block):
    """头部校验和：校验和字段按零计，整个头按字节求和取低 32 位。"""
    return (sum(block[:CHECKSUM_OFFSET]) + sum(block[CHECKSUM_END:])) & 0xFFFFFFFF


def build_header(name_bytes, data_size):
    """拼一个 512 字节头（写侧唯一入口）。"""
    head = bytearray(BLOCK_SIZE)
    head[0:NAME_OFFSET] = MAGIC
    head[NAME_OFFSET:NAME_OFFSET + len(name_bytes)] = name_bytes
    head[SIZE_OFFSET:SIZE_END] = struct.pack(">Q", data_size)
    head[CHECKSUM_OFFSET:CHECKSUM_END] = struct.pack(">I", checksum(head))
    return bytes(head)


def parse_header(block, index):
    """解析一个 512 字节头，返回 (name, data_size)；格式错误抛 ValueError。"""
    if block[:NAME_OFFSET] != MAGIC:
        raise ValueError("not an archlite archive: magic=%r" % bytes(block[:NAME_OFFSET]))
    stored = struct.unpack(">I", block[CHECKSUM_OFFSET:CHECKSUM_END])[0]
    if checksum(block) != stored:
        raise ValueError("header checksum mismatch at entry %d" % index)
    raw = block[NAME_OFFSET:NAME_END].split(b"\x00", 1)[0]
    name = raw.decode("utf-8")
    size = struct.unpack(">Q", block[SIZE_OFFSET:SIZE_END])[0]
    return name, size
