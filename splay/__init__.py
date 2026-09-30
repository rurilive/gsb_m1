"""splay: 用一个 Python 列表维护整数序列的朴素实现，纯标准库。

对外只暴露 Seq 这一个序列容器，以及 Erro 异常基类。
"""

from .seq import Erro, Seq

__all__ = ["Erro", "Seq"]
