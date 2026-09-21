"""带编码的列段页：页头记编码与 min/max，页尾带校验。

页在段里首尾相接，一页一种编码（页头 enc 字节）：

- int：
  - ENC_INT_DELTA 帧参照 + 增量：页首存本页基准（首个值），
    其余是相对页内前一值的 zigzag varint 增量，每页自带帧、可单独解；
  - ENC_INT_RAW 兜底：逐值 8 字节小端。
- str：
  - ENC_STR_DICT_PLAIN 字典 + 逐值 varint code；
  - ENC_STR_DICT_RLE 字典 + 游程 (code, run)；
  - ENC_STR_RAW 兜底：长度 varint + UTF-8。

每页自带完整字典，老页在后续字典增长后仍能单独解开；写端按字典既有
顺序给字符串编号，相邻页天然复用同一套 code。

页框架（小端）：

    [uvarint 头长][头][payload][u32 CRC32]

CRC 覆盖 头长前缀 + 头 + payload。头固定为：

    enc(u8) nrows(uvarint) payload_len(uvarint)
    min_svarint max_svarint（int）/ 带长度前缀的 min/max UTF-8（str）

页里行数由页头自描述，不依赖写端的页大小常量。
"""

import struct
import zlib

from colpage.codec import (
    decode_svarint,
    decode_uvarint,
    encode_svarint,
    encode_uvarint,
)
from colpage.errors import BadPageError, FormatError

ENC_INT_DELTA = 0
ENC_INT_RAW = 1
ENC_STR_DICT_PLAIN = 2
ENC_STR_DICT_RLE = 3
ENC_STR_RAW = 4

_CRC = struct.Struct("<I")


def _crc(blob):
    return _CRC.pack(zlib.crc32(blob) & 0xFFFFFFFF)


def _enc_int_delta(values):
    out = bytearray()
    out += encode_svarint(values[0])
    rest = (values[i] - values[i - 1] for i in range(1, len(values)))
    for delta in rest:
        out += encode_svarint(delta)
    return bytes(out)


def _dec_int_delta(payload, count):
    """帧参照页：payload 首项是本页基准（首值绝对值），其余是页内增量。"""
    pos = 0
    base, pos = decode_svarint(payload, pos)
    values = [base]
    last = base
    for _ in range(count - 1):
        delta, pos = decode_svarint(payload, pos)
        last += delta
        values.append(last)
    if pos != len(payload):
        raise FormatError("int 增量页有 %d 个多余字节" % (len(payload) - pos))
    return values


def _enc_int_raw(values):
    return b"".join(struct.pack("<q", value) for value in values)


def _dec_int_raw(payload, count):
    if len(payload) != count * 8:
        raise FormatError("int raw 页长度 %d 不是 %d 的 8 倍" % (len(payload), count))
    return [struct.unpack_from("<q", payload, index * 8)[0]
            for index in range(count)]


def _enc_str_raw(values):
    out = bytearray()
    for value in values:
        blob = value.encode("utf-8")
        out += encode_uvarint(len(blob))
        out += blob
    return bytes(out)


def _dec_str_raw(payload, count):
    values = []
    pos = 0
    for _ in range(count):
        size, pos = decode_uvarint(payload, pos)
        end = pos + size
        if end > len(payload):
            raise FormatError("str raw 页越界: 还差 %d 字节" % (end - len(payload)))
        values.append(payload[pos:end].decode("utf-8"))
        pos = end
    if pos != len(payload):
        raise FormatError("str raw 页有 %d 个多余字节" % (len(payload) - pos))
    return values


def _enc_dict(dictionary):
    out = bytearray(encode_uvarint(len(dictionary)))
    for value in dictionary:
        blob = value.encode("utf-8")
        out += encode_uvarint(len(blob))
        out += blob
    return bytes(out)


def _dec_dict(payload, pos):
    size, pos = decode_uvarint(payload, pos)
    dictionary = []
    for _ in range(size):
        blob_len, pos = decode_uvarint(payload, pos)
        end = pos + blob_len
        if end > len(payload):
            raise FormatError("字典越界: 还差 %d 字节" % (end - len(payload)))
        dictionary.append(payload[pos:end].decode("utf-8"))
        pos = end
    return dictionary, pos


def _enc_dict_plain(indexes):
    return b"".join(encode_uvarint(code) for code in indexes)


def _dec_dict_plain(payload, count, pos):
    indexes = []
    for _ in range(count):
        code, pos = decode_uvarint(payload, pos)
        indexes.append(code)
    if pos != len(payload):
        raise FormatError("字典页有 %d 个多余字节" % (len(payload) - pos))
    return indexes


def _enc_dict_rle(indexes):
    out = bytearray()
    total = 0
    run_code = indexes[0]
    run_len = 1
    for code in indexes[1:]:
        if code == run_code:
            run_len += 1
        else:
            out += encode_uvarint(run_code)
            out += encode_uvarint(run_len)
            total += run_len
            run_code = code
            run_len = 1
    out += encode_uvarint(run_code)
    out += encode_uvarint(run_len)
    total += run_len
    return encode_uvarint(total) + bytes(out)


def _dec_dict_rle(payload, count, pos):
    total, pos = decode_uvarint(payload, pos)
    if total != count:
        raise FormatError("游程页声称 %d 个值，页头是 %d" % (total, count))
    indexes = []
    while pos < len(payload):
        code, pos = decode_uvarint(payload, pos)
        run_len, pos = decode_uvarint(payload, pos)
        indexes.extend([code] * run_len)
    if pos != len(payload):
        raise FormatError("游程页有 %d 个多余字节" % (len(payload) - pos))
    if len(indexes) != count:
        raise FormatError("游程页解出 %d 个值，页头是 %d" % (len(indexes), count))
    return indexes


def _dict_indexes(values, state):
    """按字典既有顺序编号；相邻页沿用同一套 code，新值追加在后面。"""
    mapping = state.setdefault("map", {})
    dictionary = state.setdefault("dict", [])
    indexes = []
    for value in values:
        code = mapping.get(value)
        if code is None:
            code = len(dictionary)
            mapping[value] = code
            dictionary.append(value)
        indexes.append(code)
    return indexes


def _build_str_header(enc, count, payload, lo, hi):
    head = bytearray([enc])
    head += encode_uvarint(count)
    head += encode_uvarint(len(payload))
    lo_blob = lo.encode("utf-8")
    hi_blob = hi.encode("utf-8")
    head += encode_uvarint(len(lo_blob))
    head += lo_blob
    head += encode_uvarint(len(hi_blob))
    head += hi_blob
    return bytes(head)


def _build_int_header(enc, count, payload, lo, hi):
    head = bytearray([enc])
    head += encode_uvarint(count)
    head += encode_uvarint(len(payload))
    head += encode_svarint(lo)
    head += encode_svarint(hi)
    return bytes(head)


def encode_page(kind, values, state=None):
    """把一页值编成自描述的页字节，返回 (blob, state)。

    state 是跨页上下文，目前 str 用它记字典（相邻页复用 code）；
    int 的帧参照在每页自带，不依赖跨页状态，任何一页都能单独解。
    首页传 None 或空 dict 都行。
    """
    if state is None:
        state = {}
    count = len(values)
    if kind == "int":
        delta = _enc_int_delta(values)
        raw = _enc_int_raw(values)
        if len(delta) < len(raw):
            enc = ENC_INT_DELTA
            payload = delta
        else:
            enc = ENC_INT_RAW
            payload = raw
        head = _build_int_header(enc, count, payload, min(values), max(values))
    elif kind == "str":
        indexes = _dict_indexes(values, state)
        dictionary = state["dict"]
        # 页内只带本页用到的 code，但 code 编号沿用全局顺序；每页自带字典，
        # 老页字典不变、新页字典扩了也互不影响，任何一页都能单独解开。
        used = sorted(set(indexes))
        local = [dictionary[code] for code in used]
        remap = {old: new for new, old in enumerate(used)}
        local_indexes = [remap[code] for code in indexes]
        plain = _enc_dict(local) + _enc_dict_plain(local_indexes)
        rle = _enc_dict(local) + _enc_dict_rle(local_indexes)
        raw = _enc_str_raw(values)
        if len(plain) <= len(rle) and len(plain) <= len(raw):
            enc = ENC_STR_DICT_PLAIN
            payload = plain
        elif len(rle) <= len(raw):
            enc = ENC_STR_DICT_RLE
            payload = rle
        else:
            enc = ENC_STR_RAW
            payload = raw
        head = _build_str_header(enc, count, payload, min(values), max(values))
    else:
        raise FormatError("未知列类型: %r" % (kind,))
    prefix = encode_uvarint(len(head))
    frame = prefix + head + payload
    return frame + _crc(frame), state


def _read_min_max(kind, head, pos):
    if kind == "int":
        lo, pos = decode_svarint(head, pos)
        hi, pos = decode_svarint(head, pos)
        return lo, hi, pos
    lo_len, pos = decode_uvarint(head, pos)
    lo = head[pos:pos + lo_len].decode("utf-8")
    pos += lo_len
    hi_len, pos = decode_uvarint(head, pos)
    hi = head[pos:pos + hi_len].decode("utf-8")
    pos += hi_len
    return lo, hi, pos


def parse_page_header(kind, blob, offset=0, verify=True):
    """只解页头，返回 (header, next_offset)，不碰 payload 内容。

    header: dict(enc, nrows, payload_offset, payload_len, min, max)。
    verify=True 时 blob 要装得下整页并校验页尾 CRC；
    verify=False 只要求 blob 从 offset 起装得下页头，用于 min/max 跳页，
    不读 payload、不算解码。offset 已到段尾时返回 (None, offset)。
    """
    if offset >= len(blob):
        return None, offset
    start = offset
    try:
        head_len, pos = decode_uvarint(blob, offset)
        head_end = pos + head_len
        if head_end > len(blob):
            raise BadPageError("页头超出段范围", page=None)
        head = blob[pos:head_end]
        enc = head[0]
        hpos = 1
        nrows, hpos = decode_uvarint(head, hpos)
        payload_len, hpos = decode_uvarint(head, hpos)
        lo, hi, hpos = _read_min_max(kind, head, hpos)
        if hpos != len(head):
            raise FormatError("页头有 %d 个多余字节" % (len(head) - hpos))
        payload_offset = head_end
        frame_end = payload_offset + payload_len
        if verify and frame_end + 4 > len(blob):
            raise BadPageError("页 payload 超出段范围", page=None)
        if verify:
            stored = blob[frame_end:frame_end + 4]
            if _crc(blob[start:frame_end]) != stored:
                raise BadPageError("页校验不过", page=None)
    except BadPageError:
        raise
    except (IndexError, UnicodeDecodeError, FormatError, struct.error) as exc:
        raise BadPageError("页头解不开: %s" % exc, page=None)
    return ({"enc": enc, "nrows": nrows, "payload_offset": payload_offset,
             "payload_len": payload_len, "min": lo, "max": hi},
            frame_end + 4)


def decode_page(kind, blob, offset=0):
    """解一页，返回 (values, next_offset)。帧参照已写进每页 payload。"""
    header, next_offset = parse_page_header(kind, blob, offset)
    if header is None:
        return None, offset
    payload = blob[header["payload_offset"]:
                   header["payload_offset"] + header["payload_len"]]
    enc = header["enc"]
    count = header["nrows"]
    try:
        if enc == ENC_INT_RAW:
            values = _dec_int_raw(payload, count)
        elif enc == ENC_INT_DELTA:
            values = _dec_int_delta(payload, count)
        elif enc == ENC_STR_RAW:
            values = _dec_str_raw(payload, count)
        elif enc in (ENC_STR_DICT_PLAIN, ENC_STR_DICT_RLE):
            dictionary, pos = _dec_dict(payload, 0)
            if enc == ENC_STR_DICT_PLAIN:
                indexes = _dec_dict_plain(payload, count, pos)
            else:
                indexes = _dec_dict_rle(payload, count, pos)
            values = []
            for code in indexes:
                if code >= len(dictionary):
                    raise FormatError("字典 code %d 越界（字典 %d 项）"
                                      % (code, len(dictionary)))
                values.append(dictionary[code])
        else:
            raise FormatError("不认识的页编码: %d" % enc)
    except BadPageError:
        raise
    except (IndexError, UnicodeDecodeError, FormatError, struct.error) as exc:
        raise BadPageError("页 payload 解不开: %s" % exc, page=None)
    if len(values) != count:
        raise BadPageError("页解出 %d 个值，页头是 %d" % (len(values), count),
                           page=None)
    return values, next_offset
