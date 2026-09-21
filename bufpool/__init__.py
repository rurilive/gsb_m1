"""bufpool: 网关拼装报文用的进程内缓冲区分配器，纯标准库。

现状：Allocator 每次 acquire 都新分配 bytearray，release 之后直接丢掉。
"""

from bufpool.alloc import Allocator
from bufpool.buffer import Buffer
from bufpool.errors import BufpoolError, InvalidSize, UnknownBuffer
from bufpool.stats import AllocStats
from bufpool.tiers import OVERSIZE, TIERS, check_size, tier_key, tier_of

__all__ = [
    "AllocStats",
    "Allocator",
    "Buffer",
    "BufpoolError",
    "InvalidSize",
    "OVERSIZE",
    "TIERS",
    "UnknownBuffer",
    "check_size",
    "tier_key",
    "tier_of",
]
