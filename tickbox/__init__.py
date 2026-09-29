"""tickbox：纯标准库的定时器包。

当前只提供最朴素的列表式定时器集合 TimerSet 及其错误基类 TimerError。
分层时间轮的实现待补，见任务描述。
"""

from tickbox.timers import TimerError, TimerSet

__all__ = ["TimerError", "TimerSet"]
