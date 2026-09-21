"""tracesamp: 进程内的链路追踪采样器，静态比例 + 自适应限流。"""

from .clock import ManualClock
from .sampler import MODE_ADAPTIVE, MODE_STATIC, TraceSampler, trace_unit
from .window import SlidingWindow

__all__ = [
    "ManualClock",
    "MODE_ADAPTIVE",
    "MODE_STATIC",
    "SlidingWindow",
    "TraceSampler",
    "trace_unit",
]
