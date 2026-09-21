"""rbacflow：网关侧的授权策略库，纯标准库。

PolicyStore 存角色和授予，Engine 负责判定。
"""

from .actions import segments, validate
from .engine import Engine
from .errors import (
    DuplicateGrant,
    InvalidAction,
    NotGranted,
    PolicyError,
    UnknownRole,
)
from .store import PolicyStore

__all__ = [
    "DuplicateGrant",
    "Engine",
    "InvalidAction",
    "NotGranted",
    "PolicyError",
    "PolicyStore",
    "UnknownRole",
    "segments",
    "validate",
]
