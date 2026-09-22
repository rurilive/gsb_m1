"""resolvcache: 接入层用的进程内解析缓存，纯标准库。"""

from .cache import (
    DEFAULT_JITTER,
    DEFAULT_NEGATIVE_TTL,
    DEFAULT_TTL,
    ResolverCache,
)
from .clock import ManualClock, SystemClock
from .upstream import Answer, FakeUpstream, UpstreamError

__all__ = [
    "DEFAULT_JITTER",
    "DEFAULT_NEGATIVE_TTL",
    "DEFAULT_TTL",
    "ResolverCache",
    "SystemClock",
    "ManualClock",
    "Answer",
    "FakeUpstream",
    "UpstreamError",
]
