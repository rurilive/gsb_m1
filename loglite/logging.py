"""结构化日志层：级别过滤、线程上下文栈、可插拔 sink、按大小轮转。

默认配置（StreamSink + PLAIN 渲染）只输出消息正文，与各模块历史
裸 print 的 stdout 逐行一致；需要统一采集时 configure(FileSink(...))
切换成 JSONL 等结构化输出。

上下文保存在 threading.local 的栈上：set_context 压栈、clear_context
弹栈，压两层弹一层回到上一层；各线程独立，互不串扰。
"""

import json
import os
import sys
import threading

DEBUG = 10
INFO = 20
WARNING = 30
ERROR = 40

_LEVELS = {
    "DEBUG": DEBUG,
    "INFO": INFO,
    "WARNING": WARNING,
    "ERROR": ERROR,
}

PLAIN = "plain"
JSON = "json"

_lock = threading.RLock()
_level = INFO
_sinks = []


def _level_value(level):
    if isinstance(level, str):
        try:
            return _LEVELS[level.upper()]
        except KeyError:
            raise ValueError(f"unknown level: {level!r}") from None
    return level


def configure(level=None, sinks=None):
    """配置全局级别与 sink 列表；级别以下的记录不进任何 sink。"""
    global _level, _sinks
    with _lock:
        if level is not None:
            _level = _level_value(level)
        if sinks is not None:
            _sinks = list(sinks)


def get_level():
    return _level


def add_sink(sink):
    with _lock:
        _sinks.append(sink)


def reset():
    """恢复默认配置（INFO + 纯文本 stdout），主要给测试用。"""
    global _level, _sinks
    with _lock:
        _level = INFO
        _sinks = [StreamSink()]
        _local.frames = [{}]


class Record:
    __slots__ = ("level", "name", "message", "context", "thread_name")

    def __init__(self, level, name, message, context, thread_name):
        self.level = level
        self.name = name
        self.message = message
        self.context = context
        self.thread_name = thread_name


_local = threading.local()


def _frames():
    frames = getattr(_local, "frames", None)
    if frames is None:
        frames = [{}]
        _local.frames = frames
    return frames


def set_context(**fields):
    """压入一层上下文，返回可手动弹层的 token；也可作为 with 使用。

    新一层继承上一层字段，同名字段以新层为准。
    """
    frames = _frames()
    merged = dict(frames[-1])
    merged.update(fields)
    frames.append(merged)
    return _Token()


class _Token:
    __slots__ = ("released",)

    def __init__(self):
        self.released = False

    def release(self):
        if not self.released:
            frames = _frames()
            if len(frames) > 1:
                frames.pop()
            self.released = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()
        return False


def clear_context(token=None):
    """弹掉最近一层上下文（回到上一层而非清空）。

    传入 set_context 返回的 token 时弹该层；直接调用弹最近一层。
    """
    if token is None:
        frames = _frames()
        if len(frames) > 1:
            frames.pop()
        return
    token.release()


def context():
    """返回当前合并后的上下文快照（dict）。"""
    return dict(_frames()[-1])


class Logger:
    def __init__(self, name=None):
        self.name = name

    def _emit(self, level, message):
        if level < _level:
            return
        record = Record(
            level=level,
            name=self.name,
            message=message,
            context=context(),
            thread_name=threading.current_thread().name,
        )
        with _lock:
            sinks = list(_sinks)
        for sink in sinks:
            sink.write(record)

    def debug(self, message):
        self._emit(DEBUG, message)

    def info(self, message):
        self._emit(INFO, message)

    def warning(self, message):
        self._emit(WARNING, message)

    def error(self, message):
        self._emit(ERROR, message)


def get_logger(name=None):
    return Logger(name)


def _plain(record):
    return record.message + "\n"


def _json_safe(value):
    try:
        json.dumps(value)
        return value
    except TypeError:
        return repr(value)


_LEVEL_NAMES = {DEBUG: "DEBUG", INFO: "INFO", WARNING: "WARNING", ERROR: "ERROR"}


def _json(record):
    payload = {
        "level": _LEVEL_NAMES[record.level],
        "logger": record.name,
        "message": record.message,
        "thread": record.thread_name,
        "context": {key: _json_safe(val) for key, val in record.context.items()},
    }
    return json.dumps(payload, ensure_ascii=False) + "\n"


_RENDERERS = {PLAIN: _plain, JSON: _json}


def _resolve_render(render):
    return _RENDERERS[render] if isinstance(render, str) else render


class StreamSink:
    """把记录写到文本流；默认每次写时取当前 sys.stdout。

    后一种取法保证 redirect_stdout（如测试捕获）对日志同样生效。
    """

    def __init__(self, stream=None, render=PLAIN):
        self._stream = stream
        self._render = _resolve_render(render)
        self._lock = threading.Lock()

    def write(self, record):
        text = self._render(record)
        stream = self._stream if self._stream is not None else sys.stdout
        with self._lock:
            stream.write(text)
            stream.flush()


class CaptureSink:
    """内存捕获 sink：记录 Record 与渲染文本，供测试与临时采集使用。"""

    def __init__(self, render=PLAIN):
        self.records = []
        self.lines = []
        self._render = _resolve_render(render)
        self._lock = threading.Lock()

    def write(self, record):
        with self._lock:
            self.records.append(record)
            self.lines.append(self._render(record).rstrip("\n"))

    def messages(self):
        return [record.message for record in self.records]


class FileSink:
    """文件 sink：单行 JSONL（或其他渲染），当前文件超 max_bytes 即轮转。

    轮转把 path -> path.1，原 path.{n-1} 顺移到 path.{n}，只保留
    backups 个旧文件。写与轮转共用一把锁：多线程同时写爆当前文件时，
    只有一个线程执行轮转，其余线程阻塞等待，记录不丢、不轮两次。
    """

    def __init__(self, path, max_bytes=1024 * 1024, backups=5, render=JSON,
                 encoding="utf-8", on_rotate=None):
        self.path = path
        self.max_bytes = max_bytes
        self.backups = backups
        self._render = _resolve_render(render)
        self._encoding = encoding
        self._on_rotate = on_rotate
        self._lock = threading.RLock()
        self._file = None
        self._size = 0
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self._open()

    def _open(self):
        self._file = open(self.path, "ab")
        self._size = os.path.getsize(self.path)

    def write(self, record):
        data = self._render(record).encode(self._encoding)
        with self._lock:
            self._file.write(data)
            self._file.flush()
            self._size += len(data)
            if self._size >= self.max_bytes:
                self._rotate()

    def _rotate(self):
        self._file.close()
        if self.backups <= 0:
            os.remove(self.path)
        else:
            for index in range(self.backups, 0, -1):
                source = self.path if index == 1 else f"{self.path}.{index - 1}"
                target = f"{self.path}.{index}"
                if os.path.exists(source):
                    if os.path.exists(target):
                        os.remove(target)
                    os.replace(source, target)
        if self._on_rotate is not None:
            self._on_rotate()
        self._open()

    def close(self):
        with self._lock:
            if self._file is not None:
                self._file.close()
                self._file = None


reset()
