"""账本与估算器文件的编解码。

文件是一份 JSON 对象，fmt 标出格式版本：

- fmt 1（账本）：分片名做键，值是该分片内 key 的编码列表。
- fmt 2（估算器）：{"kind": "sketch", "sketch": {"bits", "seed",
  "registers"}}，桶位按 base64 落盘。

key 用带类型标签的两元列表编码：

    str   -> ["s", "u1"]
    bool  -> ["b", true]
    int   -> ["i", 7]
    bytes -> ["y", "<base64 文本>"]
    tuple -> ["t", [<元素编码>, ...]]
    None  -> ["n", null]

账本编码时会先按标签排序再写盘，同一份数据落盘两次字节完全一致。
load 按格式版本返回 Ledger 或 BucketSketch；文件缺失抛 FileNotFoundError，
内容不合法抛 ValueError。老版本写出的 fmt 1 文件依旧能读，读出后可把
key 灌进 BucketSketch 接着合并；多出来的未知字段一律忽略。
"""

import base64
import json

from dedupkit.ledger import Ledger

FMT = 1
FMT_SKETCH = 2
SUPPORTED_FMT = (FMT, FMT_SKETCH)


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


def save_sketch(sketch, path):
    """把 BucketSketch 的桶位写成 fmt 2 的 JSON 文件。"""
    from dedupkit.sketch import BucketSketch

    if not isinstance(sketch, BucketSketch):
        raise TypeError(
            f"save_sketch 只支持 BucketSketch，收到 {type(sketch).__name__}"
        )
    document = {
        "fmt": FMT_SKETCH,
        "kind": "sketch",
        "sketch": {
            "bits": sketch.bits,
            "seed": sketch.seed,
            "registers": base64.b64encode(sketch.registers()).decode("ascii"),
        },
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(document, handle, ensure_ascii=True, sort_keys=True)


def _load_sketch(document, path):
    """从 fmt 2 文档重建 BucketSketch；字段有毛病抛 ValueError。"""
    from dedupkit.sketch import (
        MAX_BITS,
        MIN_BITS,
        BucketSketch,
    )

    body = document.get("sketch")
    if not isinstance(body, dict):
        raise ValueError("fmt 2 文档缺 sketch 对象")
    bits = body.get("bits")
    seed = body.get("seed", 0)
    encoded = body.get("registers")
    if not isinstance(bits, int) or isinstance(bits, bool):
        raise ValueError(f"bits 必须是整数: {bits!r}")
    if not MIN_BITS <= bits <= MAX_BITS:
        raise ValueError(f"bits 超出支持范围: {bits!r}")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError(f"seed 必须是整数: {seed!r}")
    if not isinstance(encoded, str):
        raise ValueError("registers 必须是 base64 文本")
    try:
        data = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise ValueError(f"registers 不是合法 base64: {exc}") from exc
    expected = 2**bits
    if len(data) != expected:
        raise ValueError(
            f"桶位长度与 bits 不符: 拿到 {len(data)}，应为 {expected}（{path}）"
        )
    ceiling = 65 - bits
    if any(byte > ceiling for byte in data):
        raise ValueError(f"桶位里出现越界值，合法上限为 {ceiling}")
    return BucketSketch._from_registers(bits, seed, data)


def load(path):
    """读回账本（fmt 1）或估算器（fmt 2）。

    文件缺失抛 FileNotFoundError，内容不合法抛 ValueError。
    """
    with open(path, "r", encoding="utf-8") as handle:
        try:
            document = json.load(handle)
        except json.JSONDecodeError as exc:
            raise ValueError(f"不是合法 JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise ValueError("顶层必须是 JSON 对象")
    if "fmt" not in document:
        raise ValueError("缺 fmt 字段")
    version = document["fmt"]
    if not isinstance(version, int) or isinstance(version, bool):
        raise ValueError(f"fmt 必须是整数: {version!r}")
    if version == FMT_SKETCH:
        return _load_sketch(document, path)
    if version != FMT:
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
