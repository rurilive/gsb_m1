"""nestrun：基于事件循环的轻量任务调度器。

任务可以派生子任务、带延迟开工、带总预算超时，可整棵取消。
时间从注入的时钟读，定时器挂在事件循环的堆上。
"""

from .errors import Cancelled, InvalidTransition, SchedulerError
from .loop import EventLoop, ManualClock, TimerHandle
from .scheduler import Scheduler
from .task import (
    CANCELLED,
    FAILED,
    LEGAL_TRANSITIONS,
    PENDING,
    RUNNING,
    SETTLED_STATES,
    STATES,
    SUCCEEDED,
    Task,
    check_transition,
)

__all__ = [
    "CANCELLED",
    "Cancelled",
    "EventLoop",
    "FAILED",
    "InvalidTransition",
    "LEGAL_TRANSITIONS",
    "ManualClock",
    "PENDING",
    "RUNNING",
    "SETTLED_STATES",
    "STATES",
    "SUCCEEDED",
    "Scheduler",
    "SchedulerError",
    "Task",
    "TimerHandle",
    "check_transition",
]
