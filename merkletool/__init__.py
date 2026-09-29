"""merkletool: 一个朴素的整体哈希，纯标准库，无外部依赖。"""

from .hash import hash_bytes, hash_text, naive_root

__all__ = ["hash_bytes", "hash_text", "naive_root"]
