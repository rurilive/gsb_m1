"""事件溯源聚合的现有实现，纯标准库。

把领域里发生的事记成一串有序的领域事件，聚合自身不直接改状态，而是把事件
append 进事件流，再由 replay 把事件逐个作用到状态上。当前版本只支持最朴素的
全量重放：append 一条事件就当场重放，state 是重放的结果；replay 永远从第 0 条
事件开始，没有快照、没有版本冲突检测，也没有按区间取事件的能力。

约定：事件版本从 1 开始（第 n 条事件的 version 就是 n），version 0 约定为
空聚合的初始版本。每个聚合实例只服务一个聚合根，多次 append 的事件按顺序共享
同一条事件流。
"""

import copy
import threading


class Event:
    """一条领域事件：类型名、携带的数据、以及它在该聚合事件流里的版本号。"""

    __slots__ = ("version", "etype", "data")

    def __init__(self, version, etype, data=None):
        self.version = version
        self.etype = etype
        self.data = dict(data) if data else {}

    def __repr__(self):
        return f"Event(version={self.version}, etype={self.etype!r}, data={self.data!r})"

    def __eq__(self, other):
        if not isinstance(other, Event):
            return NotImplemented
        return (self.version == other.version and self.etype == other.etype
                and self.data == other.data)

    def __hash__(self):
        return hash((self.version, self.etype))


class ConcurrencyError(Exception):
    """版本冲突：调用方声称的 expected_version 与聚合当前版本不一致时抛出。"""

    def __init__(self, expected, actual):
        self.expected = expected
        self.actual = actual
        super().__init__(f"version conflict: expected {expected}, actual {actual}")


class Aggregate:
    """一个聚合根的事件流与状态。

    apply(event, state) 是用户提供的重放函数：给定一条事件与当前状态，返回
    应用该事件之后的新状态。缺省用 apply_default，支持常见的 set 型事件
    （data 里带 field 与 value 就写回 state 对应字段）。

    当前对外能力：
      append(etype, data=None)   追加一条事件并立刻重放，返回新版本号
      replay()                   从第 0 条事件开始全量重放，返回状态
      state                      最近一次重放得到的状态
      events()                   事件流快照（按版本升序）
      version                    当前版本（已 append 的事件条数）
    """

    def __init__(self, apply=None, initial=None):
        self._apply = apply or apply_default
        self._initial = initial
        self._events = []
        self._state = copy.deepcopy(initial) if initial is not None else {}
        self._lock = threading.RLock()

    def append(self, etype, data=None):
        """追加一条事件并立即重放到状态，返回这条事件的版本号。"""
        with self._lock:
            version = len(self._events) + 1
            event = Event(version, etype, data)
            self._events.append(event)
            self._state = self._apply(event, self._state)
            return version

    def replay(self):
        """从第 0 条事件开始全量重放，返回状态，满足初始版本的回退语义。"""
        with self._lock:
            state = copy.deepcopy(self._initial) if self._initial is not None else {}
            for event in self._events:
                state = self._apply(event, state)
            self._state = state
            return copy.deepcopy(state)

    def events(self):
        """事件流快照，按版本升序；返回的是副本，改动不影响内部。"""
        with self._lock:
            return [Event(e.version, e.etype, e.data) for e in self._events]

    @property
    def version(self):
        with self._lock:
            return len(self._events)

    @property
    def state(self):
        with self._lock:
            return copy.deepcopy(self._state)


def apply_default(event, state):
    """缺省重放函数：set 型事件按 data 里的 field 与 value 写回状态。

    没有 field 的事件视为纯记录，不改状态（状态原样返回）。
    """
    field = event.data.get("field")
    if field is None:
        return state
    state = dict(state)
    state[field] = event.data.get("value")
    return state
