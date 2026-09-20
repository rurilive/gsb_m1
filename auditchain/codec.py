"""审计记录的规范编码与内容摘要。

一条记录是字段名到值的映射，落盘时一行一条。规范编码固定键序和分隔符，
同一份内容在哪个进程里编码出的字节都完全一样，摘要才做得数。
摘要只覆盖内容本身，覆盖范围算错，老记录就全对不上了。
"""

import hashlib
import json

DIGEST_FIELD = "digest"
PREV_DIGEST_FIELD = "prev_digest"
GENESIS_DIGEST = ""


class RecordError(ValueError):
    """记录不是合法映射，或者编码出来的字节解不回去。"""


def canonical(record):
    """规范编码，返回 bytes，不带换行。

    键按字典序排，分隔符收紧，非 ASCII 一律转义，
    这样同样的内容不会因为拼接顺序不同而编出两串字节。
    """
    if not isinstance(record, dict):
        raise RecordError("record must be a mapping, got %r" % (type(record).__name__,))
    try:
        text = json.dumps(
            record, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )
    except (TypeError, ValueError) as exc:
        raise RecordError("record is not encodable: %s" % (exc,)) from exc
    return text.encode("ascii")


def encode_line(record):
    """记录编成一行，末尾带换行符。"""
    return canonical(record) + b"\n"


def decode_line(line):
    """一行解回记录，解不出来抛 RecordError。"""
    if isinstance(line, bytes):
        try:
            line = line.decode("ascii")
        except UnicodeDecodeError as exc:
            raise RecordError("line is not ascii") from exc
    try:
        record = json.loads(line)
    except ValueError as exc:
        raise RecordError("line is not json: %s" % (exc,)) from exc
    if not isinstance(record, dict):
        raise RecordError("line is not a mapping")
    return record


def content_fields(record):
    """去掉摘要字段之后剩下的部分，摘要算的就是这部分。"""
    return {key: value for key, value in record.items() if key != DIGEST_FIELD}


def record_digest(record):
    """内容摘要，sha256 十六进制小写，同一份内容结果永远一致。"""
    return hashlib.sha256(canonical(content_fields(record))).hexdigest()
