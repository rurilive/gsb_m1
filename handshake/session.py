"""会话状态机：把转移表跑起来。

- feed(event, payload=None)：外部事件入口
- poll()：定时器到点（clock() >= deadline）时合成 TIMEOUT 事件，
  走同一张表完成转移；无定时器的状态下是空操作
- clock 注入（默认 time.monotonic），日志时间戳全部来自它
"""

import time
from collections import namedtuple

from .table import TABLE
from .states import Ev, State


class ProtocolError(Exception):
    """协议违规：当前状态下不接受该事件。"""

    def __init__(self, state, event):
        super().__init__(f"状态 {state.value} 不接受事件 {event}")
        self.state = state
        self.event = event


LogEntry = namedtuple("LogEntry", "ts kind detail")
# kind: recv（收到外部事件）/ timeout（定时器到点）/
#       move（状态迁移）/ send（发出对端消息）


class Session:
    """单条会话的状态机实例。"""

    def __init__(self, clock=None):
        self._clock = clock if clock is not None else time.monotonic
        self.state = State.CLOSED
        self.suite = None
        self.log = []
        self.outbox = []
        self._deadline = None

    def feed(self, event, payload=None):
        self.log.append(LogEntry(self._clock(), "recv", event))
        self._dispatch(event, payload)

    def poll(self):
        if self._deadline is None:
            return
        if self._clock() >= self._deadline:
            self._deadline = None
            self.log.append(LogEntry(
                self._clock(), "timeout",
                f"{Ev.TIMEOUT} in {self.state.value}"))
            self._dispatch(Ev.TIMEOUT, None)

    def _match(self, event, payload):
        for row in TABLE:
            if row.state is self.state and row.event == event:
                if all(g(payload, self) for g in row.guards):
                    return row
        return None

    def _dispatch(self, event, payload):
        row = self._match(event, payload)
        if row is None:
            raise ProtocolError(self.state, event)
        src = self.state
        self.state = row.next
        self.log.append(LogEntry(
            self._clock(), "move", f"{src.value}->{row.next.value}"))
        for msg in row.sends:
            self.outbox.append((self._clock(), msg))
            self.log.append(LogEntry(self._clock(), "send", msg))
        for action in row.actions:
            action(self, payload)
        self._deadline = (
            self._clock() + row.timer) if row.timer is not None else None
