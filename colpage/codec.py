"""列段编解码，外加变长整数积木。

encode_segment / decode_segment 是列段读写的统一出入口，按编码名分发。
现在只有 raw：int 逐值 8 字节小端，str 是长度加 UTF-8 字节，不做压缩。
"""

import struct

from colpage.errors import FormatError

RAW = "raw"


def encode_uvarint(value):
    """非负整数编成 LEB128 字节串。"""
    if value < 0:
        raise ValueError("uvarint 只收非负数: %r" % (value,))
    out = bytearray()
    while value > 0x7F:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def decode_uvarint(buf, pos=0):
    """从 buf[pos] 解一个 uvarint，返回 (值, 下一个位置)。"""
    value = 0
    shift = 0
    while True:
        if pos >= len(buf):
            raise FormatError("varint 读到了缓冲区尽头")
        byte = buf[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, pos
        shift += 7
        if shift > 70:
            raise FormatError("varint 超过 64 位")


def encode_svarint(value):
    """有符号整数编成 zigzag 加 uvarint。"""
    if value >= 0:
        return encode_uvarint(value << 1)
    return encode_uvarint(((-value) << 1) - 1)


def decode_svarint(buf, pos=0):
    """解一个有符号变长整数，返回 (值, 下一个位置)。"""
    code, pos = decode_uvarint(buf, pos)
    value = code >> 1
    if code & 1:
        value = -value - 1
    return value, pos


def encode_raw(kind, values):
    """整列原始编码，不做压缩。"""
    if kind == "int":
        return b"".join(struct.pack("<q", value) for value in values)
    if kind == "str":
        out = bytearray()
        for value in values:
            blob = value.encode("utf-8")
            out += encode_uvarint(len(blob))
            out += blob
        return bytes(out)
    raise FormatError("未知列类型: %r" % (kind,))


def decode_raw(kind, buf):
    """整段原始编码解回一列值。"""
    if kind == "int":
        if len(buf) % 8:
            raise FormatError("int 列长度 %d 不是 8 的倍数" % len(buf))
        return [struct.unpack_from("<q", buf, offset)[0]
                for offset in range(0, len(buf), 8)]
    if kind == "str":
        values = []
        pos = 0
        while pos < len(buf):
            size, pos = decode_uvarint(buf, pos)
            end = pos + size
            if end > len(buf):
                raise FormatError("str 列越界: 还差 %d 字节" % (end - len(buf)))
            values.append(buf[pos:end].decode("utf-8"))
            pos = end
        return values
    raise FormatError("未知列类型: %r" % (kind,))


def encode_segment(kind, values, codec=RAW):
    """整列编码，codec 现在只认 raw。"""
    if codec == RAW:
        return encode_raw(kind, values)
    raise FormatError("不认识的编码: %r" % (codec,))


def decode_segment(kind, buf, codec=RAW):
    """整段解码，codec 现在只认 raw。"""
    if codec == RAW:
        return decode_raw(kind, buf)
    raise FormatError("不认识的编码: %r" % (codec,))
