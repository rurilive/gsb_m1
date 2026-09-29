"""beatsx：区间取最值与区间求和的雏形包。

当前只提供朴素实现 NaiveSeg；异常基类 BeatsError 一并在此导出，
供后续可能出现的更细粒度异常继承。
"""

from .seg import BeatsError, NaiveSeg

__all__ = ["BeatsError", "NaiveSeg"]
