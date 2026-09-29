"""pushbuf：最朴素的无界先进先出缓冲，纯标准库。"""

from .buffer import UnboundedBuffer

__all__ = ["UnboundedBuffer"]
