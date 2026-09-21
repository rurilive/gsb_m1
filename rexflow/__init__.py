"""rexflow：日志检索用的小正则引擎。

当前能力是字面量加星号：fullmatch 做整串匹配，search 从每个起点重试。
语法与执行都还很小，见 README 与 demo.py。
"""

from .errors import PatternError
from .matcher import Match, Pattern, fullmatch, search
from .parser import Char, Seq, Star, parse

__all__ = [
    "Char",
    "Match",
    "Pattern",
    "PatternError",
    "Seq",
    "Star",
    "compile",
    "fullmatch",
    "parse",
    "search",
]


def compile(pattern):
    """把模式串编成 Pattern，等价于 Pattern(pattern)。"""
    return Pattern(pattern)
