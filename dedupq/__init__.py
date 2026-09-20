"""dedupq：内存去重队列。"""

from .queue import DedupQueue, FakeClock

__all__ = ["DedupQueue", "FakeClock"]
