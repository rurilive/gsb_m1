"""压缩块的磁盘布局与编解码。

块文件 = 12 字节文件头（8 字节魔数 + 4 字节大端块大小）+ 若干块。
每块 = 40 字节块头 + 变长块体。块头依次是：8 字节块标记、基准时间
（int64）、末条时间戳（int64）、条数、块体长度、块体 CRC32 与 4
字节保留位。

块体前半是时间戳：首条相对基准的一阶差分，其后每条是二阶差分，
统一 zigzag 后按 LEB128 变长写。后半是值：先存首条 64 位原值，
之后每条与前一条的二进制位异或——异或为 0 只写一个 0 位；否则写
1 位、6 位有效宽度减一、再按宽度把异或值低位打包，高位在前，块体
最后一个字节不足的位补 0。
"""

import struct
import zlib

from .errors import TsFormatError

#: 块文件魔数，8 字节；与裸存魔数区分格式。
BLOCK_MAGIC = b"TSBLK01\n"

#: 块标记，每个块头都重复一遍，用来识别块头与错位。
BLOCK_MARK = b"TSBLK\x00\x00\x00"

#: 文件头：魔数 + 块大小（每块固定条数）。
FILE_HEADER = struct.Struct(">8sI")

#: 块头：标记、基准时间、末条时间、条数、块体长、CRC32、保留位。
BLOCK_HEADER = struct.Struct(">8sqqIIII")

#: varint 最多 10 字节：int64 时间戳的二阶差分 zigzag 后不超过 67 位。
MAX_VARINT_LEN = 10

_D = struct.Struct(">d")
_Q = struct.Struct(">Q")


def _double_bits(value):
    return _Q.unpack(_D.pack(float(value)))[0]


def _bits_to_double(bits):
    return _D.unpack(_Q.pack(bits & 0xFFFFFFFFFFFFFFFF))[0]


def _zigzag(n):
    # 时间戳差落在 int64 可表达的范围内，按 64 位有符号数折叠。
    return ((n << 1) ^ (n >> 63)) & 0xFFFFFFFFFFFFFFFF


def _unzigzag(u):
    return (u >> 1) ^ -(u & 1)


def _write_varint(out, n):
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return


def _read_varint(buf, pos):
    result = 0
    shift = 0
    for _ in range(MAX_VARINT_LEN):
        b = buf[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            return result, pos
        shift += 7
    raise ValueError("varint 超过 %d 字节" % MAX_VARINT_LEN)


class _BitWriter:
    """高位在前的位打包器。"""

    __slots__ = ("_buf", "_cur", "_nbits")

    def __init__(self):
        self._buf = bytearray()
        self._cur = 0
        self._nbits = 0

    def bit(self, b):
        cur = (self._cur << 1) | b
        nbits = self._nbits + 1
        if nbits == 8:
            self._buf.append(cur)
            self._cur = 0
            self._nbits = 0
        else:
            self._cur = cur
            self._nbits = nbits

    def bits(self, value, n):
        buf = self._buf
        cur = self._cur
        nbits = self._nbits
        while n > 0:
            if nbits == 0 and n >= 8:
                n -= 8
                buf.append((value >> n) & 0xFF)
                continue
            space = 8 - nbits
            if n <= space:
                cur = (cur << n) | (value & ((1 << n) - 1))
                nbits += n
                if nbits == 8:
                    buf.append(cur)
                    cur = 0
                    nbits = 0
                n = 0
            else:
                cur = (cur << space) | ((value >> (n - space)) & ((1 << space) - 1))
                buf.append(cur)
                cur = 0
                nbits = 0
                n -= space
        self._cur = cur
        self._nbits = nbits

    def finish(self):
        if self._nbits:
            self._buf.append(self._cur << (8 - self._nbits))
            self._cur = 0
            self._nbits = 0
        return bytes(self._buf)


def encode_payload(pairs):
    """把块内 (时间戳, 值) 序列编成块体字节。"""
    count = len(pairs)
    if count == 0:
        raise ValueError("空块不能编码")
    ts_part = bytearray()
    prev_delta = 0
    prev_ts = pairs[0][0]
    for i, (ts, _value) in enumerate(pairs):
        delta = ts - prev_ts
        _write_varint(ts_part, _zigzag(delta - prev_delta))
        prev_delta = delta
        prev_ts = ts

    val_part = bytearray(8)
    struct.pack_into(">Q", val_part, 0, _double_bits(pairs[0][1]))
    bw = _BitWriter()
    prev_bits = _double_bits(pairs[0][1])
    for _ts, value in pairs[1:]:
        bits = _double_bits(value)
        xor = bits ^ prev_bits
        if xor == 0:
            bw.bit(0)
        else:
            bw.bit(1)
            width = xor.bit_length()
            bw.bits(width - 1, 6)
            bw.bits(xor, width)
        prev_bits = bits
    return bytes(ts_part) + bytes(val_part) + bw.finish()


def pack_block(pairs):
    """把整块编成 块头 + 块体 的完整字节。"""
    payload = encode_payload(pairs)
    crc = zlib.crc32(payload) & 0xFFFFFFFF
    return BLOCK_HEADER.pack(
        BLOCK_MARK,
        pairs[0][0],
        pairs[-1][0],
        len(pairs),
        len(payload),
        crc,
        0,
    ) + payload


def parse_header(buf):
    """解 40 字节块头；标记不对抛 TsFormatError。"""
    mark, base_ts, last_ts, count, payload_len, crc, reserved = (
        BLOCK_HEADER.unpack(buf)
    )
    if mark != BLOCK_MARK:
        raise TsFormatError("块标记不匹配，块流错位")
    return {
        "base_ts": base_ts,
        "last_ts": last_ts,
        "count": count,
        "payload_len": payload_len,
        "crc": crc,
        "reserved": reserved,
    }


def payload_crc(buf):
    """分块也能算的 CRC32，供打开文件时流式校验。"""
    return zlib.crc32(buf) & 0xFFFFFFFF


def decode_payload(base_ts, buf, count, with_values=True):
    """解块体。with_values 为假时只解时间戳（供 find 使用）。

    任何长度不对、varint 过长或位读完了还在读都抛 ValueError，
    由调用方按坏块处理。
    """
    end = len(buf)
    pos = 0
    timestamps = [0] * count
    delta = 0
    ts = base_ts
    for i in range(count):
        b = buf[pos]
        pos += 1
        if not (b & 0x80):
            result = b
        else:
            result = b & 0x7F
            shift = 7
            for _ in range(1, MAX_VARINT_LEN):
                if pos >= end:
                    raise ValueError("时间戳段截断")
                b = buf[pos]
                pos += 1
                result |= (b & 0x7F) << shift
                if not (b & 0x80):
                    break
                shift += 7
            else:
                raise ValueError("varint 超过 %d 字节" % MAX_VARINT_LEN)
        delta += (result >> 1) ^ -(result & 1)
        ts = base_ts + delta if i == 0 else ts + delta
        timestamps[i] = ts

    if not with_values:
        return timestamps, None

    values = [0.0] * count
    if pos + 8 > end:
        raise ValueError("值首值截断")
    prev_bits = struct.unpack_from(">Q", buf, pos)[0]
    pos += 8
    prev_float = _bits_to_double(prev_bits)
    values[0] = prev_float

    bitpos = pos * 8
    total_bits = end * 8
    i = 1
    while i < count:
        # 0 位表示值不变；一段连续 0 位尽量按整字节跑批跳过。
        byte = buf[bitpos >> 3] if bitpos < total_bits else 0xFF
        lead = bitpos & 7
        part = byte << lead if lead else byte
        if part & 0x80:
            zeros = 0
        else:
            zeros = 8 - lead if part == 0 else 8 - part.bit_length()
        if zeros > 0:
            take = min(zeros, count - i)
            values[i:i + take] = [prev_float] * take
            i += take
            bitpos += take
            if i >= count:
                break
        if bitpos >= total_bits:
            raise ValueError("值位流截断")
        flag = (buf[bitpos >> 3] >> (7 - (bitpos & 7))) & 1
        bitpos += 1
        if flag == 0:
            values[i] = prev_float
            i += 1
            continue
        if bitpos + 6 > total_bits:
            raise ValueError("值位流截断")
        width = _read_bits(buf, bitpos, 6) + 1
        bitpos += 6
        if bitpos + width > total_bits:
            raise ValueError("值位流截断")
        xor = _read_bits(buf, bitpos, width)
        bitpos += width
        prev_bits = prev_bits ^ xor
        prev_float = _bits_to_double(prev_bits)
        values[i] = prev_float
        i += 1
    return timestamps, values


def _read_bits(buf, bitpos, n):
    """从字节数组的 bitpos 起读 n 位（高位在前）。"""
    result = 0
    while n > 0:
        offset = bitpos & 7
        avail = 8 - offset
        take = n if n < avail else avail
        byte = buf[bitpos >> 3]
        result = (result << take) | (
            (byte >> (avail - take)) & ((1 << take) - 1)
        )
        bitpos += take
        n -= take
    return result
