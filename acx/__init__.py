"""acx: 多模式串匹配。

当前只提供基于逐模式滑动比较的朴素 Matcher，作为自动机改造前的基线。
"""

from acx.multi import Erro, Matcher, build

__all__ = ["Erro", "Matcher", "build"]
