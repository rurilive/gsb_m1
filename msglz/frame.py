"""消息帧的打包与解包。

帧是消息在总线上传输的最小单元，自包含，收到就能解：

    b"MZ1"     3 字节魔数
    种类       1 字节：0 原文直存，1 LZ 压缩体
    raw_len    varint，原文长度
    payload    压缩体或原文
    校验和     4 字节大端，原文的 FNV-1a 32 位

校验和算的是原文，不是压缩体：压缩体再坏也能靠它兜住，解出来跟
原文对不上就报错。
"""

from .errors import FormatError
from .lz import decode_varint, encode_varint

#: 当前帧格式的魔数。
MAGIC = b"MZ1"

#: 种类：原文直存。
KIND_RAW = 0

#: 种类：LZ 压缩体。
KIND_LZ = 1

_CHECKSUM_LEN = 4


def fnv32(data):
    """FNV-1a 32 位散列，用来当帧里的校验和。"""
    value = 0x811C9DC5
    for byte in bytes(data):
        value = ((value ^ byte) * 0x01000193) & 0xFFFFFFFF
    return value


def pack_frame(kind, raw_len, payload, checksum):
    """拼一个帧。checksum 由调用方算好（原文的 fnv32）。"""
    if kind not in (KIND_RAW, KIND_LZ):
        raise ValueError("未知帧种类 %r" % (kind,))
    head = MAGIC + bytes([kind]) + encode_varint(raw_len)
    return head + bytes(payload) + checksum.to_bytes(_CHECKSUM_LEN, "big")


def unpack_frame(frame):
    """拆一个帧，返回 (kind, raw_len, payload, checksum)。"""
    frame = bytes(frame)
    if len(frame) < len(MAGIC) + 1 + 1 + _CHECKSUM_LEN:
        raise FormatError("帧只有 %d 字节，短得不像话" % len(frame))
    if not frame.startswith(MAGIC):
        raise FormatError("魔数不匹配，不是 msglz 帧")
    kind = frame[len(MAGIC)]
    if kind not in (KIND_RAW, KIND_LZ):
        raise FormatError("未知帧种类 %d" % kind)
    raw_len, pos = decode_varint(frame, len(MAGIC) + 1)
    tail = len(frame) - _CHECKSUM_LEN
    if pos > tail:
        raise FormatError("帧在头部就断了")
    payload = frame[pos:tail]
    checksum = int.from_bytes(frame[tail:], "big")
    if kind == KIND_RAW and len(payload) != raw_len:
        raise FormatError(
            "直存帧带 %d 字节，头部却说原文有 %d 字节" % (len(payload), raw_len)
        )
    return kind, raw_len, payload, checksum
