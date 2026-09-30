"""sqrtds: 一个可变序列上的朴素操作工具。

当前只有平铺列表实现，见 sqrtds/seq.py。区间加、区间求和、区间最大值
与区间计数都把整段逐个重扫一遍，单点查询直接读数组，规模一大就慢。
分块（根号分治）与另一条独立做法的改造见任务描述。
"""

from sqrtds.seq import (
    EmptyRangeError,
    IndexOutOfRangeError,
    Sequence,
    SqrtdsError,
)

__all__ = [
    "Sequence",
    "SqrtdsError",
    "EmptyRangeError",
    "IndexOutOfRangeError",
]
