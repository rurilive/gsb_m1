"""catalanx：卡特兰数与合法括号序列的朴素求解器。

现状实现全部走在最直白的笨路上：求第 n 个卡特兰数时用求和形式的递推式，对每个
下标再把两侧的卡特兰数各自递归展开，重复子问题被反复计算；枚举长度为 2n 的合法
括号序列时，先把二的 2n 次方条候选串全部生成出来，再对每一条用栈模拟判定；判断
一个括号串是否合法靠逐字符栈模拟；求一个合法序列的合法前缀计数，则对每一个前缀
单独重判一遍。规模一上去就按指数或二的次方量级膨胀，但结果正确、口径固定。
"""

from catalanx.core import (
    Catalanx,
    CatalanxError,
    InvalidBracketError,
    OutOfRangeError,
    TypeMismatchError,
)

__all__ = [
    "Catalanx",
    "CatalanxError",
    "InvalidBracketError",
    "OutOfRangeError",
    "TypeMismatchError",
]
