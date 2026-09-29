"""snapstore: 多键一致性快照存储，纯标准库，无外部依赖。

当前只有逐键 KV 基线，见 snapstore/kv.py。跨键原子快照、写时复制、
写写冲突检测与快照回收见任务描述。
"""

from snapstore.kv import KeyValueStore

__all__ = ["KeyValueStore"]