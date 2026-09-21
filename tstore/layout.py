"""裸存磁盘布局：8 字节魔数头加定长记录。

文件 = 魔数头 + N 条定长记录，每条 16 字节：8 字节大端有符号整数
时间戳，8 字节 IEEE754 双精度值。记录条数直接由文件长度推出，头里
不另存条数。

本模块只管单条记录的打包解包与头部校验，不碰文件句柄。
"""

import struct

from .errors import TsFormatError

#: 裸存文件的魔数头，正好 8 字节。
HEADER = b"TSRAW01\n"

#: 一条记录 16 字节，小端：int64 时间戳 + float64 值。
RECORD = struct.Struct("<qd")


def pack_record(ts, value):
    """把一条 (时间戳, 值) 打成 16 字节。"""
    return RECORD.pack(ts, value)


def unpack_record(buf):
    """把 16 字节解成 (时间戳, 值)。"""
    return RECORD.unpack(buf)


def record_count(file_size):
    """按文件长度算记录条数，长度对不上布局就抛 TsFormatError。"""
    body = file_size - len(HEADER)
    if body < 0 or body % RECORD.size:
        raise TsFormatError(
            "文件长度 %d 与布局不符（应为 %d 加 16 的整数倍）"
            % (file_size, len(HEADER))
        )
    return body // RECORD.size


def validate_header(buf):
    """校验头 8 字节；不是本格式直接抛 TsFormatError。"""
    if buf != HEADER:
        raise TsFormatError("文件头魔数不匹配，不是 tstore 裸存文件")
