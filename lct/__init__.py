"""lct: 用邻接表与深搜维护一片森林的朴素实现，纯标准库。

对外只暴露 Forest 这一个森林容器，以及 Erro 异常基类。
"""

from .forest import Erro, Forest

__all__ = ["Erro", "Forest"]
