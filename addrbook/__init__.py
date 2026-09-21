"""addrbook: 纯标准库的 IPv4 地址池管理。

现在提供扁平地址池 AddressPool，以及地址文本互转和网段计算
的辅助函数，见 addrbook.address。
"""

from addrbook.address import (
    ADDR_MAX,
    block_size,
    broadcast_of,
    check_prefix,
    format_addr,
    format_cidr,
    network_of,
    parse_addr,
    parse_cidr,
    usable_bounds,
)
from addrbook.errors import (
    AddressInUse,
    AddressNotAllocated,
    OutOfRange,
    PoolError,
    PoolExhausted,
)
from addrbook.pool import AddressPool

__all__ = [
    "ADDR_MAX",
    "AddressInUse",
    "AddressNotAllocated",
    "AddressPool",
    "OutOfRange",
    "PoolError",
    "PoolExhausted",
    "block_size",
    "broadcast_of",
    "check_prefix",
    "format_addr",
    "format_cidr",
    "network_of",
    "parse_addr",
    "parse_cidr",
    "usable_bounds",
]
