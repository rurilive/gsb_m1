"""minrot: 循环字符串工具的朴素实现。

当前只有逐起点枚举这一条路：最小字典序循环旋转按每个起点截出等长
子串再逐个比较，循环同构按一个串的全部旋转与另一个串逐个比对，最大
字典序旋转与最短位移同样靠枚举。见 minrot/naive.py，线性做法见任务
描述。
"""

from minrot.naive import (
    Erro,
    RotError,
    RotTools,
    is_rotation,
    max_rotation,
    min_rotation,
    min_rotation_index,
)

__all__ = [
    "Erro",
    "RotError",
    "RotTools",
    "is_rotation",
    "max_rotation",
    "min_rotation",
    "min_rotation_index",
]
