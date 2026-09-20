"""状态、事件与定时器常量。

状态用 Enum；事件用字符串常量（Ev 的属性即事件名）。
TIMEOUT 不是对端事件，由 Session.poll() 在定时器到点时合成。
"""

from enum import Enum


class State(Enum):
    CLOSED = "CLOSED"
    HELLO_SENT = "HELLO_SENT"
    KEY_SENT = "KEY_SENT"
    AUTH_SENT = "AUTH_SENT"
    FULL = "FULL"
    DEGRADED = "DEGRADED"


# 稳态：握手完成后会话长期停留的状态
STEADY_STATES = frozenset({State.FULL, State.DEGRADED})


class Ev:
    START = "START"
    PEER_HELLO = "PEER_HELLO"
    PEER_KEY = "PEER_KEY"
    PEER_AUTH_OK = "PEER_AUTH_OK"
    PEER_AUTH_FAIL = "PEER_AUTH_FAIL"
    PEER_CLOSE = "PEER_CLOSE"
    TIMEOUT = "TIMEOUT"


# 各握手阶段的定时器（秒），进入对应状态时武装
T_HELLO = 3.0
T_KEY = 3.0
T_AUTH = 3.0

# 加密套件：对端在 PEER_HELLO 的 payload 里指定
# strong -> 认证通过进 FULL；weak -> 认证通过进 DEGRADED
SUITES = ("strong", "weak")
