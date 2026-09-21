"""流式哈希工具，读文件时内存占用只跟分块大小有关。"""

import hashlib

READ_CHUNK = 1 << 16


def hash_bytes(data):
    """字节串的 sha256 十六进制摘要。"""
    return hashlib.sha256(data).hexdigest()


def hash_file(path, chunk_size=READ_CHUNK):
    """流式计算整份文件的 sha256。

    按 chunk_size 一块块读取，不把文件整份读进内存。
    chunk_size 不是正整数抛 ValueError。
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()
