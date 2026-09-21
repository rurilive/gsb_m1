"""rbacflow：网关侧的授权策略库，纯标准库。

PolicyStore 存角色、授予、拒绝和继承边，Engine 负责判定与解释。
"""

from .actions import (
    candidates,
    is_wildcard,
    matches,
    pattern_parts,
    segments,
    validate,
    validate_pattern,
)
from .engine import Engine
from .engine import Explanation
from .errors import (
    DuplicateDeny,
    DuplicateGrant,
    InheritanceCycle,
    InvalidAction,
    NotGranted,
    PolicyError,
    UnknownRole,
)
from .store import PolicyStore

__all__ = [
    "DuplicateDeny",
    "DuplicateGrant",
    "Engine",
    "Explanation",
    "InheritanceCycle",
    "InvalidAction",
    "NotGranted",
    "PolicyError",
    "PolicyStore",
    "UnknownRole",
    "candidates",
    "is_wildcard",
    "matches",
    "pattern_parts",
    "segments",
    "validate",
    "validate_pattern",
]
