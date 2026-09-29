"""taskq：带优先级与延迟的任务调度器（纯标准库）。

当前包里只有一个朴素的先进先出队列 FifoQueue。
"""

from .queue import FifoQueue

__all__ = ["FifoQueue"]