"""块压缩编码：时间戳二阶差分变长编码，值异或后按位打包。

一个块 = 28 字节块头 + 负载。块头：基准时间 int64、末条时间 int64、
条数 uint32、负载字节数 uint32、CRC32 uint32（覆盖前四个头字段与负载，
头里任何字段被改都会校验不过）。负载 = 时间戳字节流 + 值位流：

- 时间戳：第一条存与基准的差（恒为 0），之后每条存相邻差分的二阶
  差分，zigzag 转无符号后 LEB128 变长编码；
- 值：逐条与前一条的 float64 位型异或，为 0 写 1 个比特 0，否则写
  比特 1、6 比特前导零位数、6 比特有效位数减一、再写有效位本身
  （类 Gorilla）。块内第一条值写完整 64 比特。

本模块只管单块的编解码与校验，不碰文件句柄。
"""

import struct
import zlib

#: 块头布局：基准时间、末条时间、条数、负载长度、负载 CRC32。
BLOCK_HEADER = struct.Struct("<qqIII")

#: CRC32 覆盖的头字段部分（前四个字段，不含 CRC 自己）。
_CRC_SCOPE = struct.Struct("<qqII")

_F64 = struct.Struct("<d")
_U64 = struct.Struct("<Q")

#: 变长整数最多读多少字节，超出视为坏数据。
_VARINT_MAX_BYTES = 64


class BlockError(Exception):
    """块负载解不出来（截断或内容损坏）。"""


def _zigzag_encode(n):
    return (n << 1) if n >= 0 else ((-n) << 1) - 1


def _zigzag_decode(z):
    return (z >> 1) ^ -(z & 1)


def _write_uvarint(out, n):
    while n > 0x7F:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    out.append(n)


def _read_uvarint(buf, pos):
    value = 0
    shift = 0
    for _ in range(_VARINT_MAX_BYTES):
        if pos >= len(buf):
            raise BlockError("变长整数截断")
        byte = buf[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            return value, pos
        shift += 7
    raise BlockError("变长整数过长")


class _BitWriter:
    """大端序位流写出器，不满一字节时右侧补零。"""  # 位流内部约定，对外不可见

    def __init__(self):
        self._acc = 0
        self._nbits = 0
        self._out = bytearray()

    def write(self, value, nbits):
        self._acc = (self._acc << nbits) | (value & ((1 << nbits) - 1))
        self._nbits += nbits
        while self._nbits >= 8:
            self._nbits -= 8
            self._out.append((self._acc >> self._nbits) & 0xFF)
        self._acc &= (1 << self._nbits) - 1

    def finish(self):
        if self._nbits:
            self._out.append((self._acc << (8 - self._nbits)) & 0xFF)
            self._acc = 0
            self._nbits = 0
        return bytes(self._out)


class _BitReader:
    def __init__(self, data, bit_pos=0):
        self._data = data
        self._pos = bit_pos

    def read(self, nbits):
        if self._pos + nbits > len(self._data) * 8:
            raise BlockError("值位流截断")
        value = 0
        while nbits:
            bit_off = self._pos & 7
            take = min(nbits, 8 - bit_off)
            shift = 8 - bit_off - take
            chunk = (self._data[self._pos >> 3] >> shift) & ((1 << take) - 1)
            value = (value << take) | chunk
            self._pos += take
            nbits -= take
        return value


def check_crc(header_buf, payload):
    """校验块头与负载：头长度够、CRC 对得上。不抛异常，返回布尔。"""
    if len(header_buf) != BLOCK_HEADER.size:
        return False
    crc = BLOCK_HEADER.unpack(header_buf)[4]
    expect = zlib.crc32(header_buf[: _CRC_SCOPE.size])
    expect = zlib.crc32(payload, expect) & 0xFFFFFFFF
    return expect == crc


def encode_block(pairs):
    """把一串 (时间戳, 值) 编成完整的一块（块头 + 负载）。"""
    if not pairs:
        raise ValueError("空块不编码")
    base_ts = pairs[0][0]
    last_ts = pairs[-1][0]
    ts_part = bytearray()
    _write_uvarint(ts_part, 0)
    prev_ts = base_ts
    prev_delta = 0
    for ts, _ in pairs[1:]:
        delta = ts - prev_ts
        _write_uvarint(ts_part, _zigzag_encode(delta - prev_delta))
        prev_delta = delta
        prev_ts = ts
    writer = _BitWriter()
    prev_bits = None
    for _, value in pairs:
        bits = _U64.unpack(_F64.pack(value))[0]
        if prev_bits is None:
            writer.write(bits, 64)
        else:
            xor = bits ^ prev_bits
            if xor == 0:
                writer.write(0, 1)
            else:
                leading = 64 - xor.bit_length()
                trailing = (xor & -xor).bit_length() - 1
                significant = 64 - leading - trailing
                writer.write(1, 1)
                writer.write(leading, 6)
                writer.write(significant - 1, 6)
                writer.write(xor >> trailing, significant)
        prev_bits = bits
    payload = bytes(ts_part) + writer.finish()
    count = len(pairs)
    crc = zlib.crc32(_CRC_SCOPE.pack(base_ts, last_ts, count, len(payload)))
    crc = zlib.crc32(payload, crc) & 0xFFFFFFFF
    header = BLOCK_HEADER.pack(base_ts, last_ts, count, len(payload), crc)
    return header + payload


def decode_block(base_ts, count, payload):
    """把块负载解回 (时间戳, 值) 列表；数据损坏抛 BlockError。"""
    if count <= 0:
        raise BlockError("条数必须为正")
    timestamps = []
    pos = 0
    prev_ts = base_ts
    prev_delta = 0
    for i in range(count):
        zz, pos = _read_uvarint(payload, pos)
        if i == 0:
            prev_ts = base_ts + _zigzag_decode(zz)
        else:
            prev_delta += _zigzag_decode(zz)
            prev_ts += prev_delta
        timestamps.append(prev_ts)
    reader = _BitReader(payload, pos * 8)
    values = []
    prev_bits = None
    for _ in range(count):
        if prev_bits is None:
            bits = reader.read(64)
        elif reader.read(1) == 0:
            bits = prev_bits
        else:
            leading = reader.read(6)
            significant = reader.read(6) + 1
            if leading + significant > 64:
                raise BlockError("值位流损坏")
            bits = prev_bits ^ (reader.read(significant) << (64 - leading - significant))
        values.append(_F64.unpack(_U64.pack(bits))[0])
        prev_bits = bits
    return list(zip(timestamps, values))
