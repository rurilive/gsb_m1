"""resolvcache: 接入层用的进程内解析缓存，纯标准库。"""

from .cache import (
    DEFAULT_JITTER,
    DEFAULT_NEGATIVE_TTL,
    DEFAULT_TTL,
    REFRESH_FRACTION,
    ResolverCache,
)
from .clock import ManualClock, SystemClock
from .upstream import Answer, FakeUpstream, UpstreamError

__all__ = [
    "DEFAULT_TTL",
    "DEFAULT_NEGATIVE_TTL",
    "DEFAULT_JITTER",
    "REFRESH_FRACTION",
    "ResolverCache",
    "SystemClock",
    "ManualClock",
    "Answer",
    "FakeUpstream",
    "UpstreamError",
]
