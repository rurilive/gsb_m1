"""bittrie: 改造前的朴素异或集合实现。

对外只暴露 FlatXorMax, 一切查询都在一个整数列表上从头到尾线性扫描。
"""
from .xorcol import Erro, FlatXorMax, NonNegativeIntError, EmptyCollectionError, MissingElementError, TooFewElementsError

__all__ = [
    "Erro",
    "FlatXorMax",
    "NonNegativeIntError",
    "EmptyCollectionError",
    "MissingElementError",
    "TooFewElementsError",
]
