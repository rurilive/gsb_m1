"""mutexly: 进程内互斥器工具。

当前只提供朴素本地锁 LocalLock，是分布式互斥改造前的基线。
"""

from mutexly.lock import LocalLock

__all__ = ["LocalLock"]
