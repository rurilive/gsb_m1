"""sketchlib: 纯标准库的频次统计小工具包。

当前只有一个精确计数器 ExactCounter，见 sketch 模块。
"""

from .sketch import ExactCounter, SketchError

__all__ = ["ExactCounter", "SketchError"]
