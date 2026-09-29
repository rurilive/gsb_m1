"""replog：一个纯标准库的单机追加日志。

当前对外能力只有 LocalLog 这一个最朴素的单机日志：append 追加一条并返回
自增序号，按序号读回条目，末尾可截断，带一个已经列到哪儿的提交位置标记。
副本、主从复制、任期与选举、冲突回退与崩溃恢复都留待在这个基础上补齐。
"""

from .log import Entry, InvalidIndex, LocalLog, RepLogError, UnknownNode

__all__ = [
    "Entry",
    "InvalidIndex",
    "LocalLog",
    "RepLogError",
    "UnknownNode",
]
