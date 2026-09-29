"""slabbin: 进程内对象借还池。

当前只提供最朴素的对象借还池 BorrowPool，按尺寸分档的内存池分配器见任务描述（待实现）。
"""

from slabbin.pool import Block, BorrowPool

__all__ = ["Block", "BorrowPool"]
