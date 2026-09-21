"""bufpool 的异常类型。"""


class BufpoolError(Exception):
    """本包的基类异常。"""


class InvalidSize(BufpoolError):
    """请求的容量不是正整数。"""


class UnknownBuffer(BufpoolError):
    """释放的缓冲不在本分配器的借出记录里。"""
