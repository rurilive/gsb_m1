"""maxrect: 纯标准库的零一网格子矩形工具包（当前为改造前基线）。

导出 MaxRect 与全部异常类型。
"""

from .rect import (
    MaxRect,
    Erro,
    ShapeErro,
    ValueErro,
    MONOTONIC,
    SUSPEND,
    NAIVE,
)

__all__ = [
    "MaxRect",
    "Erro",
    "ShapeErro",
    "ValueErro",
    "MONOTONIC",
    "SUSPEND",
    "NAIVE",
]
