"""addrbook 的异常体系。

业务错误的基类是 PoolError：请求的地址落在池外报 OutOfRange，
指定分配的地址已经被人用着报 AddressInUse，归还一个并未分配
的地址报 AddressNotAllocated，池里没有空间报 PoolExhausted。
"""


class PoolError(Exception):
    """addrbook 业务错误的基类。"""


class OutOfRange(PoolError):
    """地址或者网段落在池的覆盖范围之外。"""


class AddressInUse(PoolError):
    """请求的地址已经在用。"""


class AddressNotAllocated(PoolError):
    """请求归还的地址并未分配出去。"""


class PoolExhausted(PoolError):
    """池里找不到可分配的空间。"""
