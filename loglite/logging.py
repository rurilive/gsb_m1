"""结构化日志层。

- 级别 DEBUG / INFO / WARNING / ERROR，低于全局级别的记录不进 sink。
- 上下文保存在 threading.local 里，set_context 压栈、返回的 token
  退出或 clear 时弹栈，线程间互不串扰。
- sink 负责落盘：StreamSink（兼容模式裸消息，逐行等同 print）、
  RotatingFileSink（按大小轮转，写与轮转共用一把锁，不丢不重）。
- 默认配置就是兼容模式：各模块原有前缀仍写在消息里，渲染不加装饰，
  动态写当前 sys.stdout，与旧 print 逐字节一致。
"""

import json
import os
import sys
import threading
import time

DEBUG = 10
INFO = 20
WARNING = 30
ERROR = 40

LEVEL_NAMES = {
    DEBUG: "DEBUG",
    INFO: "INFO",
    WARNING: "WARNING",
    ERROR: "ERROR",
}
NAME_LEVELS = {name: value for value, name in LEVEL_NAMES.items()}

_RESERVED_KEYS = ("time", "level", "levelno", "msg", "name")


def resolve_level(level):
    """把级别名（大小写不敏感）或数值归一为数值级别。"""
    if isinstance(level, int):
        if level not in LEVEL_NAMES:
            raise ValueError(f"unknown log level: {level!r}")
        return level
    if isinstance(level, str):
        try:
            return NAME_LEVELS[level.upper()]
        except KeyError:
            raise ValueError(f"unknown log level: {level!r}") from None
    raise TypeError(f"level must be int or str, got {type(level).__name__}")


# ---------------------------------------------------------------------------
# 线程上下文：压栈/弹栈，嵌套时弹一层回到上一层
# ---------------------------------------------------------------------------

_local = threading.local()


def _frames():
    stack = getattr(_local, "stack", None)
    if stack is None:
        stack = []
        _local.stack = stack
    return stack


class ContextToken:
    """set_context 返回的令牌：可手动 clear，也可作为上下文管理器。"""

    def __init__(self, frame, fields):
        self._frame = frame
        self._released = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.clear()
        return False

    def clear(self):
        """只弹本帧，恢复上一层上下文；重复调用无效。"""
        if self._released:
            return
        self._released = True
        stack = _frames()
        if stack and stack[-1] is self._frame:
            stack.pop()


def set_context(**fields):
    """压入一层上下文，返回 ContextToken（可 with 或手动 clear）。"""
    frame = dict(fields)
    _frames().append(frame)
    return ContextToken(frame, fields)


def clear_context():
    """弹出最内层一层上下文（通常传 token.clear；这里提供手动弹栈）。"""
    stack = _frames()
    if stack:
        stack.pop()


def reset_context():
    """清掉当前线程全部上下文层。"""
    _local.stack = []


def get_context():
    """当前线程合并后的上下文（外层字段被内层同名字段覆盖）。"""
    merged = {}
    for frame in _frames():
        merged.update(frame)
    return merged


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------

def render_plain(record):
    """带装饰的结构化文本：`time LEVEL name | msg k=v ...`。"""
    parts = [
        f"{record['time']:.3f}",
        record["level"],
        record["name"],
        record["msg"],
    ]
    for key, value in record.items():
        if key in _RESERVED_KEYS:
            continue
        parts.append(f"{key}={value}")
    return " | ".join(parts)


def render_compat(record):
    """无装饰：只取消息文本，与旧 print 逐行一致。"""
    return record["msg"]


def render_json(record):
    """JSON Lines，供统一采集消费。"""
    return json.dumps(record, ensure_ascii=False, sort_keys=True)


# ---------------------------------------------------------------------------
# Sink
# ---------------------------------------------------------------------------

class StreamSink:
    """写文本流；stream 为 None 时动态写当前 sys.stdout（便于重定向）。"""

    def __init__(self, stream=None, renderer=render_compat):
        self._stream = stream
        self._renderer = renderer
        self._lock = threading.Lock()

    def emit(self, record):
        line = self._renderer(record)
        with self._lock:
            stream = self._stream if self._stream is not None else sys.stdout
            stream.write(line + "\n")


class RotatingFileSink:
    """按大小轮转的文件 sink。

    当前文件超过 max_bytes 后轮转：path -> path.1，path.1 -> path.2，
    依次后移，只保留最近 backups 个旧文件。写入与轮转共用一把锁，
    多线程同时写爆时只有一个线程执行轮转，其余线程等待，日志不丢、
    同一文件不会被轮两次。
    """

    def __init__(
        self,
        path,
        max_bytes,
        backups,
        renderer=render_json,
        encoding="utf-8",
    ):
        self.path = path
        self.max_bytes = max_bytes
        self.backups = backups
        self._renderer = renderer
        self._encoding = encoding
        self._lock = threading.RLock()
        self._file = open(path, "a", encoding=encoding, newline="\n")
        self._file.flush()
        self._size = self._current_size()

    def _current_size(self):
        self._file.flush()
        return os.path.getsize(self.path)

    def emit(self, record):
        line = self._renderer(record)
        data = (line + "\n").encode(self._encoding)
        with self._lock:
            if self._size > 0 and self._size + len(data) > self.max_bytes:
                self._do_rollover()
            self._file.write(line + "\n")
            self._file.flush()
            self._size += len(data)

    def _do_rollover(self):
        """在持锁状态下轮转一次；测试可覆写 _on_rollover 定节奏。"""
        self._on_rollover()

        self._file.close()
        if self.backups <= 0:
            os.remove(self.path)
        else:
            for index in range(self.backups, 0, -1):
                source = self.path if index == 1 else f"{self.path}.{index - 1}"
                target = f"{self.path}.{index}"
                if os.path.exists(source):
                    os.replace(source, target)
        self._file = open(self.path, "a", encoding=self._encoding, newline="\n")
        self._size = 0

    def _on_rollover(self):
        """轮转钩子（测试用 Event 定节奏时覆写）。"""

    def close(self):
        with self._lock:
            self._file.close()


class CaptureSink:
    """测试用：捕获完整 record 与渲染后文本行。"""

    def __init__(self, renderer=render_plain):
        self.records = []
        self.lines = []
        self._renderer = renderer

    def emit(self, record):
        self.records.append(dict(record))
        self.lines.append(self._renderer(record))


class FanoutSink:
    """一条记录扇出给多个 sink（sink 各自负责自身线程安全）。"""

    def __init__(self, sinks):
        self.sinks = list(sinks)

    def emit(self, record):
        for sink in self.sinks:
            sink.emit(record)


# ---------------------------------------------------------------------------
# Logger 与全局配置
# ---------------------------------------------------------------------------

class Logger:
    def __init__(self, name, state):
        self.name = name
        self._state = state

    def _emit(self, levelno, msg, extra):
        if levelno < self._state.level:
            return
        record = {
            "time": time.time(),
            "level": LEVEL_NAMES[levelno],
            "levelno": levelno,
            "name": self.name,
            "msg": msg,
        }
        record.update(get_context())
        for key, value in extra.items():
            if key in _RESERVED_KEYS:
                raise ValueError(f"reserved context key: {key!r}")
            record[key] = value
        self._state.sink.emit(record)

    def debug(self, msg, **extra):
        self._emit(DEBUG, msg, extra)

    def info(self, msg, **extra):
        self._emit(INFO, msg, extra)

    def warning(self, msg, **extra):
        self._emit(WARNING, msg, extra)

    def error(self, msg, **extra):
        self._emit(ERROR, msg, extra)


class _State:
    def __init__(self):
        self.level = INFO
        self.sink = StreamSink()


_state = _State()
_loggers = {}
_loggers_lock = threading.Lock()


def configure(level=None, sink=None):
    """配置全局级别与 sink；sink 可传单个或可迭代的 sink。"""
    if level is not None:
        _state.level = resolve_level(level)
    if sink is not None:
        if isinstance(sink, (list, tuple)):
            sink = FanoutSink(sink)
        _state.sink = sink


def set_level(level):
    _state.level = resolve_level(level)


def get_level():
    return _state.level


def reset_defaults():
    """恢复默认配置（INFO + 兼容模式 stdout sink）。"""
    _state.level = INFO
    _state.sink = StreamSink()
    reset_context()


def get_logger(name="loglite"):
    with _loggers_lock:
        logger = _loggers.get(name)
        if logger is None:
            logger = Logger(name, _state)
            _loggers[name] = logger
    return logger
