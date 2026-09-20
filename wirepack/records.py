"""定长记录模型与 16 字节记录的编解码。

线上格式（单条记录 16 字节，全部大端）：

    偏移  长度  字段
    0     4     seq    无符号 32 位，上游分配器只发 800 万以内的位点
    4     1     kind   1=data, 2=ack, 3=ctrl
    5     1     flags  保留位，读写两端原样透传
    6     10    label  ASCII，右侧用 NUL 补齐

记录定长，读取端按固定步长滑窗即可；seq 的取值范围是上游给的硬保证，
解析时顺带拿它做一次廉价的错位检查。
"""

import struct

from wirepack.errors import DecodeError, EncodeError

RECORD_SIZE = 16
LABEL_SIZE = 10
MAX_SEQ = 8000000

KINDS = ("data", "ack", "ctrl")
KIND_CODES = {"data": 1, "ack": 2, "ctrl": 3}
CODE_KINDS = {code: kind for kind, code in KIND_CODES.items()}

_HEAD = struct.Struct(">IBB")


class Record:
    """一条定长记录。label 是 str，flags 是 0 到 255 的整数。"""

    __slots__ = ("seq", "kind", "label", "flags")

    def __init__(self, seq, kind, label="", flags=0):
        self.seq = seq
        self.kind = kind
        self.label = label
        self.flags = flags

    def __eq__(self, other):
        if not isinstance(other, Record):
            return NotImplemented
        return (self.seq, self.kind, self.label, self.flags) == (
            other.seq, other.kind, other.label, other.flags)

    def __hash__(self):
        return hash((self.seq, self.kind, self.label))

    def __repr__(self):
        return "Record(seq=%r, kind=%r, label=%r, flags=%r)" % (
            self.seq, self.kind, self.label, self.flags)


def check_seq(seq):
    """seq 必须落在分配器保证的区间里，否则编解码两端都不认。"""
    if isinstance(seq, bool) or not isinstance(seq, int):
        raise EncodeError("seq 需要整数，收到 %r" % (seq,))
    if not 0 <= seq < MAX_SEQ:
        raise EncodeError("seq 超出分配器范围 [0, %d): %r" % (MAX_SEQ, seq))
    return seq


def encode_label(label):
    """把 label 编成补齐到 10 字节的 ASCII 字节串。"""
    if not isinstance(label, str):
        raise EncodeError("label 需要 str，收到 %r" % (label,))
    try:
        raw = label.encode("ascii")
    except UnicodeEncodeError:
        raise EncodeError("label 只能是 ASCII: %r" % (label,))
    if len(raw) > LABEL_SIZE:
        raise EncodeError("label 最长 %d 字节，收到 %d 字节"
                          % (LABEL_SIZE, len(raw)))
    return raw + b"\x00" * (LABEL_SIZE - len(raw))


def decode_label(raw):
    """还原 label，补齐区混入非 NUL 字节视为错位。"""
    head, sep, tail = bytes(raw).partition(b"\x00")
    if sep and tail.strip(b"\x00"):
        raise DecodeError("label 补齐区混入非 NUL 字节", field="label")
    try:
        return head.decode("ascii")
    except UnicodeDecodeError:
        raise DecodeError("label 不是合法 ASCII", field="label")


def pack_record(record):
    """把 Record 编成 16 字节。值不合法抛 EncodeError。"""
    seq = check_seq(record.seq)
    code = KIND_CODES.get(record.kind)
    if code is None:
        raise EncodeError("未知 kind %r" % (record.kind,))
    flags = record.flags
    if isinstance(flags, bool) or not isinstance(flags, int) or not 0 <= flags <= 255:
        raise EncodeError("flags 需要 0 到 255 的整数，收到 %r" % (flags,))
    return _HEAD.pack(seq, code, flags) + encode_label(record.label)


def unpack_record(data, offset=0):
    """从字节串的 offset 处解出一条记录，返回 (Record, next_offset)。

    数据不够或字段不合法抛 DecodeError，异常带 offset 与 field。
    """
    if offset < 0 or offset + RECORD_SIZE > len(data):
        raise DecodeError("记录不完整: 需要 %d 字节，只剩 %d 字节"
                          % (RECORD_SIZE, len(data) - offset),
                          offset=offset, field="record")
    seq, code, flags = _HEAD.unpack_from(data, offset)
    if seq >= MAX_SEQ:
        raise DecodeError("seq %d 超出分配器范围，疑似错位" % (seq,),
                          offset=offset, field="seq")
    kind = CODE_KINDS.get(code)
    if kind is None:
        raise DecodeError("未知 kind 编码 %d" % (code,), offset=offset + 4,
                          field="kind")
    raw = bytes(data[offset + 6:offset + RECORD_SIZE])
    try:
        label = decode_label(raw)
    except DecodeError as exc:
        exc.offset = offset + 6
        raise
    return Record(seq, kind, label, flags), offset + RECORD_SIZE
