"""sparsetable: 静态区间最值工具。

当前只有改造前的朴素实现，见 sparsetable/rmq.py。它内部只留一个整数列表，
每问一次区间就把区间从头到尾逐项扫一遍，取最小值、取最大值、取最小值下标
各自重扫，没有预处理、没有下标缓存、没有二维结构、也没有批量共享。

升级到稀疏表、另起一条朴素独立路径、边界与确定性，见任务描述。
"""

from sparsetable.rmq import (
    Erro,
    IllegalArgument,
    NaiveRMQ,
)

__all__ = [
    "Erro",
    "IllegalArgument",
    "NaiveRMQ",
]
