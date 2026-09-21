"""segpile: 分段存储引擎，写入进活动段，压缩把旧段归并。"""

from .backend import MemoryBackend
from .device import SimDevice
from .segment import Segment, merge_pairs, merge_units
from .store import CompactReport, Store

__all__ = [
    "Store",
    "CompactReport",
    "Segment",
    "MemoryBackend",
    "SimDevice",
    "merge_pairs",
    "merge_units",
]
