"""sufauto: 子串统计工具包。

当前只提供基于朴素枚举的 SubstringStats，作为后缀自动机改造前的基线：
求本质不同子串个数、某子串出现次数、最长重复子串、子串是否存在，
都靠枚举全部起点与全部子串完成，结果正确但规模一大就是平方量级。
"""

from sufauto.substat import SubstringStats

__all__ = ["SubstringStats"]
