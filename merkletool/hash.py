"""merkletool 的现有实现。

当前只有一套朴素的全量哈希：把逐个条目的哈希按顺序拼成一条字节串，
再对它整体求一次摘要，作为整份数据的指纹。没有树、没有分层结构，
改一个条目就得从头重算，也拿不出任何可以单独校验的凭据。
"""

import hashlib


def hash_bytes(data):
    """对一段字节求 SHA-256 摘要，返回 64 位小写十六进制。"""
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("data must be bytes")
    return hashlib.sha256(bytes(data)).hexdigest()


def hash_text(text):
    """对一段文本按 UTF-8 求摘要，返回 64 位小写十六进制。"""
    if not isinstance(text, str):
        raise TypeError("text must be str")
    return hash_bytes(text.encode("utf-8"))


def naive_root(leaves):
    """把整份列表串成一条字节串求一次摘要，作为根指纹。

    leaves 是一个可迭代对象，元素可以是 str、bytes 或已经算好的
    十六进制摘要字符串。空列表返回空串的摘要，语义固定：
    没有条目时指纹仍是一个确定的、非空的值。
    """
    chunks = []
    for leaf in leaves:
        chunks.append(_leaf_digest(leaf))
    joined = b"".join(chunks)
    return hash_bytes(joined)


def _leaf_digest(leaf):
    """把一个条目归一成字节串，供 naive_root 拼接。"""
    if isinstance(leaf, str):
        return leaf.encode("utf-8")
    if isinstance(leaf, (bytes, bytearray)):
        return bytes(leaf)
    raise TypeError("leaf must be str or bytes")
