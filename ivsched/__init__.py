"""ivsched：区间调度与区间集合统计的朴素实现。

现状把所有结论都压在一条最直白的路上：枚举区间下标的全集子集，再逐对判断是否
重叠，留下不重叠的子集里最大最重的那一批。口径直白、结果确定，但代价随区间数
指数级上涨。异常统一从 Erro 派生。
"""

from ivsched.core import (
    BadInterval,
    BadWeight,
    Erro,
    NaiveIntervalScheduler,
    UnknownInterval,
)

__all__ = [
    "BadInterval",
    "BadWeight",
    "Erro",
    "NaiveIntervalScheduler",
    "UnknownInterval",
]
