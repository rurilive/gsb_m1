"""chunkheap: 进程内大块分配器。

当前只提供最朴素的一进一出大块分配器 BumpAlloc（分配从末尾切一块，
释放是空操作）。带空闲链、相邻合并、对齐与碎片统计的扩展见任务描述
（待实现）。
"""

from chunkheap.alloc import AllocError, BumpAlloc, HeapError

__all__ = ["AllocError", "BumpAlloc", "HeapError"]
