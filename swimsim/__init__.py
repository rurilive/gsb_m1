"""swimsim：一个纯标准库的成员关系协议。

当前对外能力是 Node：一张静态成员表加整表广播，成员是否存活取决于外部
观察。心跳与失败探测、怀疑与死亡三态、版本化传播、反熵与故障恢复都留待
在这个基础上补齐。
"""

from .clock import ManualClock
from .errors import (
    DefinitionError,
    IllegalTransition,
    NotHeartbeatTime,
    SelfProbeRejected,
    SwimError,
    UnknownMember,
)
from .member import MemberRecord
from .node import Node

__all__ = [
    "DefinitionError",
    "IllegalTransition",
    "ManualClock",
    "MemberRecord",
    "Node",
    "NotHeartbeatTime",
    "SelfProbeRejected",
    "SwimError",
    "UnknownMember",
]