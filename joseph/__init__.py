"""joseph：约瑟夫环淘汰过程的工具雏形。

对外只暴露一个模拟器类与四个异常类型，方便调用方统一捕获。
"""

from .core import (
    InvalidCountError,
    Josephus,
    JosephusError,
    PositionError,
    StartConventionError,
)

__all__ = [
    "InvalidCountError",
    "Josephus",
    "JosephusError",
    "PositionError",
    "StartConventionError",
]
