"""handshake: 长连接会话的握手状态机。

转移表驱动 + 注入时钟 + 事件日志，纯标准库。
"""

from .session import LogEntry, ProtocolError, Session
from .states import STEADY_STATES, Ev, State, SUITES, T_AUTH, T_HELLO, T_KEY
from .table import Row, TABLE

__all__ = [
    "LogEntry",
    "ProtocolError",
    "Session",
    "STEADY_STATES",
    "Ev",
    "State",
    "SUITES",
    "T_AUTH",
    "T_HELLO",
    "T_KEY",
    "Row",
    "TABLE",
]
