"""区间统计工具包（改造前基线：每个询问都重扫区间）。"""

from .naive import (
    Erro,
    InvalidArgumentError,
    InvalidQueryError,
    IntervalStats,
    Prepared,
    collapsed_intervals,
    normalize_queries,
    prepare,
    scan_steps,
)

__all__ = [
    "IntervalStats",
    "Prepared",
    "prepare",
    "normalize_queries",
    "collapsed_intervals",
    "scan_steps",
    "Erro",
    "InvalidArgumentError",
    "InvalidQueryError",
]
