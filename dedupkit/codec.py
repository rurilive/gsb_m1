"""账本文件的编解码。

文件是一份 JSON 对象，fmt 标出格式版本，当前版本是 1：分片名做键，
值是该分片内 key 的编码列表。key 用带类型标签的两元列表编码：

    str   -> ["s", "u1"]
    bool  -> ["b", true]
    int   -> ["i", 7]
    bytes -> ["y", "<base64 文本>"]
    tuple -> ["t", [<元素编码>, ...]]
    None  -> ["n", null]

编码时会先按标签排序再写盘，同一份账本落盘两次字节完全一致。
load 返回 Ledger；文件缺失抛 FileNotFoundError，内容不合法抛 ValueError。
"""

import base64
import json

from dedupkit.ledger import Ledger

FMT = 1


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


def save(ledger, path):
    """把账本写成 JSON 文件，分片名与 key 都按序排好。"""
    if not isinstance(ledger, Ledger):
        raise TypeError(f"save 目前只支持 Ledger，收到 {type(ledger).__name__}")
    document = {
        "fmt": FMT,
        "shards": {name: _encode_shard(ledger.keys(name)) for name in ledger.names()},
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(document, handle, ensure_ascii=True, sort_keys=True)


def load(path):
    """读回账本；文件缺失抛 FileNotFoundError，内容不合法抛 ValueError。"""
    with open(path, "r", encoding="utf-8") as handle:
        try:
            document = json.load(handle)
        except json.JSONDecodeError as exc:
            raise ValueError(f"不是合法 JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise ValueError("顶层必须是 JSON 对象")
    if "fmt" not in document:
        raise ValueError("缺 fmt 字段")
    if document["fmt"] != FMT:
        raise ValueError(f"不认识的格式版本: {document['fmt']!r}")
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
