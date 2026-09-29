"""aclib: 一个纯标准库的多模式字典匹配小工具包。

当前对外暴露 dict 模块中的朴素实现 BruteDict 及其异常基类 DictError。
"""

from .dict import BruteDict, DictError, InvalidPatternError

__all__ = ["BruteDict", "DictError", "InvalidPatternError"]
