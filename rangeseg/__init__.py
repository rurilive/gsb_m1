"""rangeseg: 一条整数序列上的朴素区间操作工具。

当前只有平铺列表实现，见 rangeseg/seq.py。区间求和、区间加、区间最值
都把整段重扫一遍，单点读改直接落到那一格，规模一大就慢。带懒标记的
线段树改造见任务描述。
"""

from rangeseg.seq import (
    EmptySequenceError,
    IndexOutOfRangeError,
    RangeSegError,
    RangeSeq,
)

__all__ = [
    "RangeSeq",
    "RangeSegError",
    "IndexOutOfRangeError",
    "EmptySequenceError",
]
