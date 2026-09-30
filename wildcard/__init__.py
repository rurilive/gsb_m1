"""wildcard: 改造前的朴素通配符匹配实现。

对外只暴露 NaiveWildcard, 一切匹配都用最直白的递归回溯完成, 星号逐个试错。
"""
from .matcher import (
    Erro,
    NaiveWildcard,
    PatternError,
    TypeMismatchError,
    NoMatchError,
    star_lengths,
)

__all__ = [
    "Erro",
    "NaiveWildcard",
    "PatternError",
    "TypeMismatchError",
    "NoMatchError",
    "star_lengths",
]
