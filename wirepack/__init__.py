"""wirepack: 跟端上设备对接的二进制记录编解码小库。

当前线上跑的是 16 字节定长记录，编解码、按块喂入的流式解码器都在这里。
"""

from wirepack.errors import DecodeError, EncodeError, WireError
from wirepack.records import (
    KINDS,
    LABEL_SIZE,
    MAX_SEQ,
    RECORD_SIZE,
    Record,
    decode_label,
    encode_label,
    pack_record,
    unpack_record,
)
from wirepack.stream import RecordStream, chunked, iter_records

__all__ = [
    "DecodeError",
    "EncodeError",
    "KINDS",
    "LABEL_SIZE",
    "MAX_SEQ",
    "RECORD_SIZE",
    "Record",
    "RecordStream",
    "WireError",
    "chunked",
    "decode_label",
    "encode_label",
    "iter_records",
    "pack_record",
    "unpack_record",
]
