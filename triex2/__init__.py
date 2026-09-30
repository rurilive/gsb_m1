"""triex2: 朴素字符串前缀集合工具。

当前对外提供 FlatPrefixSet, 全部查询都在一份字符串列表上线性扫描。
改造目标是以字典树为核心的前缀统计工具集, 详见 README。
"""

from .trie import (
    EmptyError,
    FlatPrefixSet,
    NotFoundError,
    TrieError,
)

__all__ = ["FlatPrefixSet", "TrieError", "EmptyError", "NotFoundError"]
