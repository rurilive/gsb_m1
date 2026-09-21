"""账本与估算器文件的编解码。

文件是一份 JSON 对象，fmt 标出格式版本，当前版本是 1：分片名做键，
值是该分片内 key 的编码列表。key 用带类型标签的两元列表编码：

    str   -> ["s", "u1"]
    bool  -> ["b", true]
    int   -> ["i", 7]
    bytes -> ["y", "<base64 文本>"]
    tuple -> ["t", [<元素编码>, ...]]
    None  -> ["n", null]

编码时会先按标签排序再写盘，同一份账本落盘两次字节完全一致。
fmt 2 是估算器格式：kind 固定为 "sketch"，带 bits、seed 与 base64 编码
的桶值。读文件时两个版本都认，同版本内多出来的未知字段直接忽略。
load 按版本返回 Ledger 或 BucketSketch；文件缺失抛 FileNotFoundError，
内容不合法抛 ValueError。
"""

import base64
import json

from dedupkit.ledger import Ledger
from dedupkit.sketch import BucketSketch

FMT = 1
SKETCH_FMT = 2


def _encode_key(key):
    """把一个 key 编码成 [标签, 载荷]；不支持的类型抛 ValueError。"""
    if key is None:
        return ["n", None]
    if isinstance(key, bool):
        return ["b", key]
    if isinstance(key, str):
        return ["s", key]
    if isinstance(key, int):
        return ["i", key]
    if isinstance(key, (bytes, bytearray)):
        return ["y", base64.b64encode(bytes(key)).decode("ascii")]
    if isinstance(key, tuple):
        return ["t", [_encode_key(item) for item in key]]
    raise ValueError(f"不支持的 key 类型: {type(key).__name__}")


def _decode_key(payload):
    """把 [标签, 载荷] 还原成 key；标签不认识或载荷有毛病抛 ValueError。"""
    if not isinstance(payload, list) or len(payload) != 2:
        raise ValueError(f"key 编码必须是两元列表: {payload!r}")
    tag, value = payload
    if tag == "n":
        if value is not None:
            raise ValueError(f"null 载荷必须是 None: {payload!r}")
        return None
    if tag == "b":
        if not isinstance(value, bool):
            raise ValueError(f"bool 载荷必须是布尔值: {payload!r}")
        return value
    if tag == "s":
        if not isinstance(value, str):
            raise ValueError(f"str 载荷必须是字符串: {payload!r}")
        return value
    if tag == "i":
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"int 载荷必须是整数: {payload!r}")
        return value
    if tag == "y":
        if not isinstance(value, str):
            raise ValueError(f"bytes 载荷必须是 base64 文本: {payload!r}")
        try:
            return base64.b64decode(value, validate=True)
        except Exception as exc:
            raise ValueError(f"bytes 载荷不是合法 base64: {payload!r}") from exc
    if tag == "t":
        if not isinstance(value, list):
            raise ValueError(f"tuple 载荷必须是列表: {payload!r}")
        return tuple(_decode_key(item) for item in value)
    raise ValueError(f"不认识的 key 标签: {tag!r}")


def _encode_shard(keys):
    encoded = [_encode_key(key) for key in keys]
    encoded.sort()  # 标签打头，同标签下载荷必然同型，排序稳定
    return encoded


def _encode_sketch(sketch):
    return {
        "fmt": SKETCH_FMT,
        "kind": "sketch",
        "bits": sketch.bits,
        "seed": sketch.seed,
        "registers": base64.b64encode(sketch.registers()).decode("ascii"),
    }


def save(obj, path):
    """把账本或估算器写成 JSON 文件，内容按序排好，字节稳定。"""
    if isinstance(obj, Ledger):
        document = _encode_ledger(obj)
    elif isinstance(obj, BucketSketch):
        document = _encode_sketch(obj)
    else:
        raise TypeError(f"save 只支持 Ledger 或 BucketSketch，收到 {type(obj).__name__}")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(document, handle, ensure_ascii=True, sort_keys=True)


def _encode_ledger(ledger):
    document = {
        "fmt": FMT,
        "shards": {name: _encode_shard(ledger.keys(name)) for name in ledger.names()},
    }
    return document


def load(path):
    """读回账本或估算器；文件缺失抛 FileNotFoundError，内容不合法抛 ValueError。"""
    with open(path, "r", encoding="utf-8") as handle:
        try:
            document = json.load(handle)
        except json.JSONDecodeError as exc:
            raise ValueError(f"不是合法 JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise ValueError("顶层必须是 JSON 对象")
    if "fmt" not in document:
        raise ValueError("缺 fmt 字段")
    if document["fmt"] == FMT:
        return _decode_ledger(document)
    if document["fmt"] == SKETCH_FMT:
        return _decode_sketch(document)
    raise ValueError(f"不认识的格式版本: {document['fmt']!r}")


def _decode_ledger(document):
    shards = document.get("shards")
    if not isinstance(shards, dict):
        raise ValueError("shards 必须是对象")
    ledger = Ledger()
    for name, entries in shards.items():
        if not isinstance(entries, list):
            raise ValueError(f"分片 {name!r} 的内容必须是列表")
        for entry in entries:
            ledger.add(name, _decode_key(entry))
    return ledger


def _decode_sketch(document):
    if document.get("kind") != "sketch":
        raise ValueError(f"kind 必须是 'sketch': {document.get('kind')!r}")
    bits = document.get("bits")
    seed = document.get("seed")
    payload = document.get("registers")
    if not isinstance(bits, int) or isinstance(bits, bool):
        raise ValueError(f"bits 必须是整数: {bits!r}")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError(f"seed 必须是整数: {seed!r}")
    if not isinstance(payload, str):
        raise ValueError(f"registers 必须是 base64 文本: {payload!r}")
    try:
        registers = base64.b64decode(payload, validate=True)
    except Exception as exc:
        raise ValueError(f"registers 不是合法 base64: {payload!r}") from exc
    try:
        return BucketSketch.from_registers(bits, seed, registers)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"估算器参数不合法: {exc}") from exc
