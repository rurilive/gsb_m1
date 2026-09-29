"""gclab: 内存堆上的朴素回收实验室。

眼下只有引用计数一层，见 gclab/heap.py。标记清扫、三色标记、分代、
终结器与弱引用都还没有，见任务描述。
"""

from gclab.heap import GCError, RefCountHeap

__all__ = ["RefCountHeap", "GCError"]
