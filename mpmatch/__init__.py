"""mpmatch: 多模式串查找的朴素实现。

当前只有逐模式、逐位置直接比对的实现，见 mpmatch/automaton.py。
字典树搭配失败指针的多模式自动机、逐位置结尾命中集合与命中汇总
见任务描述。
"""

from mpmatch.automaton import Erro, Matcher, PatternError

__all__ = ["Erro", "PatternError", "Matcher"]
