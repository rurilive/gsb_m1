"""logstore: 内存字典式 KV 存储，纯标准库，无外部依赖。"""

from .store import KVStore

__all__ = ["KVStore"]