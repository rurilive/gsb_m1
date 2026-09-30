"""dsu：不相交集合与动态连通性的朴素实现。

现状用代表元到成员列表的字典维护集合，合并时逐元素改名，查询时逐元素线性扫描，
带权偏移逐元素重算，环检测靠一次线性扫描的归属查询。口径直白、结果确定，但每次
合并与查询的代价随集合规模线性增长。异常统一从 Erro 派生。
"""

from dsu.core import (
    BadElement,
    BadWeight,
    Erro,
    NaiveDisjointSets,
    NotConnected,
    UnknownNode,
)

__all__ = [
    "BadElement",
    "BadWeight",
    "Erro",
    "NaiveDisjointSets",
    "NotConnected",
    "UnknownNode",
]
