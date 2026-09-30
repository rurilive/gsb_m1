"""mobius: 莫比乌斯反演与数对计数的朴素实现。

当前只有逐数枚举的一路实现，见 mobius/mobius.py。
一趟线性筛同时筛出质数、莫比乌斯函数与最小质因子，再按倍数贡献用类似
埃氏筛的调和级数方式对多个倍数做前缀累加，见任务描述。
"""

from mobius.mobius import Erro, Inversion, NumberRangeError, ValueTypeError

__all__ = ["Erro", "Inversion", "NumberRangeError", "ValueTypeError"]
