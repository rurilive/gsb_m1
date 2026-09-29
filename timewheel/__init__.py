"""timewheel：纯标准库的定时器包。

当前只提供最朴素的线性定时器 SimpleTimer 及其错误基类 TimerError。
分层时间轮的实现待补，见任务描述。
"""

from timewheel.wheel import TimerError, SimpleTimer

__all__ = ["TimerError", "SimpleTimer"]
