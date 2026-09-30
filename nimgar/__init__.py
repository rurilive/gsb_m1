"""nimgar: 取石子游戏的必胜判定与基本组合游戏的朴素求解器。

现状实现全部走同一条笨路：对每个局面递归枚举全部走法判赢输，求必胜的最少
步数也靠递归枚举，判断多个子游戏的和时把状态整体拼接后递归。规模一大就指数
级重复计算，但结果正确、口径固定。
"""

from nimgar.core import (
    Erro,
    NimGar,
    ParamErro,
    RuleErro,
    StateErro,
)

__all__ = ["Erro", "NimGar", "ParamErro", "RuleErro", "StateErro"]
