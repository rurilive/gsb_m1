"""跨线程调用链上下文：correlation-id 传播、span 计时、树形汇总报告。

入口用 begin_chain() 开一条链路（自动生成 correlation-id），链路内用
span(name) 计时；TracedThread / TracedThreadPoolExecutor 把当前链路
上下文带进工作线程，子 span 跨线程也挂回父 span 下。每条链路的上下文
按线程各自持有副本，并发链路互不串号。
"""

import contextlib
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar

_DEFAULT_SLOW_THRESHOLD = 0.5

_current = ContextVar("tracectx_current", default=None)

_slow_threshold = _DEFAULT_SLOW_THRESHOLD


class Chain:
    """一条调用链：一个 correlation-id 加树上全部根 span。"""

    def __init__(self, correlation_id):
        self.correlation_id = correlation_id
        self.roots = []
        self._lock = threading.Lock()

    def _attach_root(self, span):
        with self._lock:
            self.roots.append(span)

    def report(self):
        """整棵 span 树的缩进文本，每行：name、耗时、慢标记。"""
        lines = ["chain %s:" % self.correlation_id]
        for root in self.roots:
            _format_span(root, 0, lines)
        return "\n".join(lines)

    def print_report(self, file=None):
        print(self.report(), file=file)


class _State:
    """单个执行点看到的链路视图；每个被包装的线程拿自己的一份。"""

    __slots__ = ("chain", "current_span")

    def __init__(self, chain, current_span=None):
        self.chain = chain
        self.current_span = current_span


def _capture():
    """快照当前上下文，供跨线程搬运；返回 (chain, current_span) 或 None。"""
    state = _current.get()
    if state is None:
        return None
    return (state.chain, state.current_span)


def _install(captured):
    """在本线程装入快照的副本，返回可复位的 token。"""
    chain, parent_span = captured
    return _current.set(_State(chain, parent_span))


@contextlib.contextmanager
def begin_chain(correlation_id=None):
    """开启一条调用链，缺省生成 uuid4 hex 作为 correlation-id。

    用法：with begin_chain() as chain: ...，结束后 chain.report()
    给出整棵 span 树。已在链路内再开链抛 RuntimeError，防止串号。
    """
    if _current.get() is not None:
        raise RuntimeError("already inside a chain")
    chain = Chain(correlation_id or uuid.uuid4().hex)
    token = _current.set(_State(chain))
    try:
        yield chain
    finally:
        _current.reset(token)


def correlation_id():
    """当前链路的 correlation-id，不在链路内返回 None。"""
    state = _current.get()
    return state.chain.correlation_id if state is not None else None


def current_chain():
    """当前 Chain 对象，不在链路内返回 None。"""
    state = _current.get()
    return state.chain if state is not None else None


def current_span():
    """当前正在计时的 Span，没有则返回 None。"""
    state = _current.get()
    return state.current_span if state is not None else None


def set_slow_threshold(seconds):
    """设置慢 span 阈值（秒），耗时 >= 阈值的 span 打慢标记。"""
    global _slow_threshold
    if seconds < 0:
        raise ValueError("slow threshold must be >= 0")
    _slow_threshold = float(seconds)


def get_slow_threshold():
    """当前慢 span 阈值（秒）。"""
    return _slow_threshold


class Span:
    """一段具名计时：monotonic 起止，嵌套挂到当前 span 下。

    由 span() 创建，作上下文管理器使用；退出时定格耗时并按阈值
    打 slow 标记。children 按开始顺序记录子 span（含跨线程归位的）。
    """

    def __init__(self, name, slow_threshold=None):
        self.name = name
        self.parent = None
        self.children = []
        self.start = None
        self.end = None
        self.slow = False
        self._slow_threshold = slow_threshold
        self._lock = threading.Lock()
        self._state = None
        self._prev = None
        self._owns_chain_token = None

    @property
    def elapsed(self):
        """耗时秒数；还在计时则算到当前时刻。"""
        if self.start is None:
            return 0.0
        stop = self.end if self.end is not None else time.monotonic()
        return stop - self.start

    def _attach(self, span):
        with self._lock:
            self.children.append(span)

    def __enter__(self):
        state = _current.get()
        if state is None:
            # 链路外单独用 span：隐式开一条链，根 span 退出时收尾
            chain = Chain(uuid.uuid4().hex)
            token = _current.set(_State(chain))
            self._owns_chain_token = token
            state = _current.get()
        self._state = state
        self._prev = state.current_span
        self.parent = self._prev
        self.start = time.monotonic()
        if self.parent is not None:
            self.parent._attach(self)
        else:
            state.chain._attach_root(self)
        state.current_span = self
        return self

    def __exit__(self, exc_type, exc, tb):
        self.end = time.monotonic()
        threshold = self._slow_threshold
        if threshold is None:
            threshold = _slow_threshold
        self.slow = self.elapsed >= threshold
        self._state.current_span = self._prev
        if self._owns_chain_token is not None:
            _current.reset(self._owns_chain_token)
        return False


def span(name, slow_threshold=None):
    """开一个名为 name 的计时 span，slow_threshold 可覆盖全局慢阈值。"""
    return Span(name, slow_threshold=slow_threshold)


def _format_span(node, depth, lines):
    mark = " [SLOW]" if node.slow else ""
    lines.append("%s%s %.1fms%s" % ("  " * depth, node.name, node.elapsed * 1000, mark))
    for child in node.children:
        _format_span(child, depth + 1, lines)


def format_report(chain=None):
    """chain 的树形报告文本；缺省取当前链路，不在链路内返回空串。"""
    if chain is None:
        chain = current_chain()
    if chain is None:
        return ""
    return chain.report()


class TracedThread(threading.Thread):
    """threading.Thread 包装器：start 时把当前链路上下文带进新线程。

    新线程拿到的是上下文副本：子 span 挂到父线程当时的 span 下，
    但线程间各自的 current_span 互不影响，并发链路不串号。
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._tracectx_captured = None

    def start(self):
        self._tracectx_captured = _capture()
        super().start()

    def run(self):
        captured = self._tracectx_captured
        if captured is None:
            return super().run()
        token = _install(captured)
        try:
            return super().run()
        finally:
            _current.reset(token)


class TracedThreadPoolExecutor(ThreadPoolExecutor):
    """ThreadPoolExecutor 包装器：submit 的任务携带提交时的链路上下文。"""

    def submit(self, fn, *args, **kwargs):
        captured = _capture()
        if captured is None:
            return super().submit(fn, *args, **kwargs)

        def _traced(*a, **kw):
            token = _install(captured)
            try:
                return fn(*a, **kw)
            finally:
                _current.reset(token)

        return super().submit(_traced, *args, **kwargs)
