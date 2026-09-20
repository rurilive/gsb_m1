"""跨线程调用链上下文：correlation-id 传播、嵌套 span 计时、树形报告。

上下文建立在线程隔离的 contextvars 之上：

- ``start_trace`` 在入口生成 correlation-id，并打开根 span；
- ``span`` / ``current_span`` 打开的子 span 自动挂到当前 span 下；
- ``TracedThread`` 与 ``TracedThreadPoolExecutor`` 在任务派发时
  抓取当前上下文快照，任务在工作线程里恢复快照后再执行——因此包装
  出来的任务自动携带当前链路 id，各条并发链路互不串号；
- 跨线程打开的子 span 归位到派发线程当时的当前 span 下。

没有活动链路时，``span`` 与 ``current_span`` 返回空操作 span，
不计时、不挂树，库代码可以无条件埋点。
"""

import contextvars
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

SLOW_MARKER = "SLOW"
RUNNING_MARKER = "RUNNING"

_current_trace = contextvars.ContextVar("tracectx_trace", default=None)
_current_span = contextvars.ContextVar("tracectx_span", default=None)


def new_trace_id():
    """生成一个新的 correlation-id（uuid4 的 hex）。"""
    return uuid.uuid4().hex


def current_trace_id():
    """返回当前线程所在链路的 id；没有活动链路时返回 None。"""
    trace = _current_trace.get()
    return None if trace is None else trace.trace_id


def current_trace():
    """返回当前线程的 Trace；没有活动链路时返回 None。"""
    return _current_trace.get()


class Span:
    """一段命名计时区间，可嵌套、可跨线程归属。

    span 在创建（``__enter__``）时启动 monotonic 计时，退出时结束；
    耗时超过所属 trace 的慢阈值即打慢标记。优先用 ``with`` /
    ``span(name)`` 使用，也可手动 ``begin`` / ``finish``。
    """

    def __init__(self, name, trace, parent=None, slow_threshold=None):
        self.name = name
        self.trace = trace
        self.parent = parent
        self.slow_threshold = (
            trace.slow_threshold if slow_threshold is None else slow_threshold
        )
        self.start = time.monotonic()
        self.end = None
        self.duration = None
        self.slow = False
        self.children = []

    def _attach(self):
        if self.parent is not None:
            self.parent.children.append(self)

    def __enter__(self):
        token_span = _current_span.set(self)
        token_trace = _current_trace.set(self.trace)
        self._span_token = token_span
        self._trace_token = token_trace
        return self

    def __exit__(self, exc_type, exc, tb):
        self.finish()
        _current_span.reset(self._span_token)
        _current_trace.reset(self._trace_token)
        return False

    def begin(self):
        """把本 span 压成当前 span，返回自身。与 finish 配对手动使用。"""
        self._span_token = _current_span.set(self)
        self._trace_token = _current_trace.set(self.trace)
        return self

    def finish(self):
        """结束计时并计算慢标记；重复调用只认第一次。"""
        if self.end is not None:
            return
        self.end = time.monotonic()
        self.duration = self.end - self.start
        if self.slow_threshold is not None and self.duration > self.slow_threshold:
            self.slow = True

    def elapsed(self):
        """已耗时（秒）：已结束返回最终耗时，进行中返回到当前的耗时。"""
        if self.duration is not None:
            return self.duration
        return time.monotonic() - self.start


class _NullSpan:
    """无活动链路时的空操作 span：不计时、不挂树、不报错。"""

    name = None
    trace = None
    parent = None
    slow = False
    duration = None
    children = ()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def begin(self):
        return self

    def finish(self):
        pass

    def elapsed(self):
        return 0.0


_NULL_SPAN = _NullSpan()


class Trace:
    """一条调用链：一个 correlation-id 加一棵 span 树。

    构造即生成 id 并打开与链路同名的根 span；根 span 的子节点即各段
    工作。慢阈值 ``slow_threshold``（秒）对全链路 span 生效，单个
    span 可用自己的阈值覆盖。``report`` 按嵌套层级缩进渲染整棵树。
    """

    def __init__(self, name="trace", trace_id=None, slow_threshold=None):
        self.name = name
        self.trace_id = new_trace_id() if trace_id is None else trace_id
        self.slow_threshold = slow_threshold
        self._lock = threading.Lock()
        self.root = Span(name, self, parent=None)
        self._closed = False

    def new_span(self, name, parent=None, slow_threshold=None):
        """在本链路下创建一个子 span。

        parent 缺省挂到根 span。span 只创建不入栈，需要计时区间请
        直接 ``with span(name)``。
        """
        child = Span(
            name,
            self,
            parent=self.root if parent is None else parent,
            slow_threshold=slow_threshold,
        )
        with self._lock:
            child._attach()
        return child

    def __enter__(self):
        self._span_token = _current_span.set(self.root)
        self._trace_token = _current_trace.set(self)
        return self

    def __exit__(self, exc_type, exc, tb):
        _current_span.reset(self._span_token)
        _current_trace.reset(self._trace_token)
        self.close()
        return False

    def close(self):
        """结束整棵树：关闭尚未 finish 的 span（含根）。幂等。"""
        if self._closed:
            return
        self._closed = True

        def _finish(span):
            for child in span.children:
                _finish(child)
            span.finish()

        with self._lock:
            _finish(self.root)

    def _render(self):
        lines = []

        def _walk(span, depth):
            indent = "  " * depth
            marks = []
            if span.slow:
                marks.append(SLOW_MARKER)
            if span.duration is None:
                marks.append(RUNNING_MARKER)
            suffix = (" [" + ",".join(marks) + "]") if marks else ""
            lines.append(
                "%s%s %.3fs%s" % (indent, span.name, span.elapsed(), suffix)
            )
            with self._lock:
                children = list(span.children)
            for child in children:
                _walk(child, depth + 1)

        _walk(self.root, 0)
        return lines

    def report(self):
        """返回树形报告字符串：每行 name、耗时（秒）、慢标记，按层级缩进。"""
        header = "trace %s (%s)" % (self.name, self.trace_id)
        return header + "\n" + "\n".join(self._render())

    def print_report(self):
        """收尾一次打出整棵树。"""
        print(self.report())


def start_trace(name="trace", trace_id=None, slow_threshold=None):
    """在入口开启一条新链路，返回 Trace 上下文管理器。

    典型用法::

        with start_trace("batch-job", slow_threshold=0.1) as trace:
            ...
        trace.print_report()
    """
    return Trace(name=name, trace_id=trace_id, slow_threshold=slow_threshold)


def current_span():
    """返回当前 span；没有活动链路时返回空操作 span。"""
    return _current_span.get() or _NULL_SPAN


def span(name, slow_threshold=None):
    """打开一个子 span，挂到当前 span 下（跨线程亦归位）。

    没有活动链路时返回空操作上下文，可安全无条件埋点。
    """
    trace = _current_trace.get()
    current = _current_span.get()
    if trace is None:
        return _NULL_SPAN
    return trace.new_span(name, parent=current, slow_threshold=slow_threshold)


def wrap(fn):
    """把当前上下文（链路 id + 当前 span）快照打包进可调用对象。

    包装结果在任何线程执行时，先恢复快照再调用原函数，执行完恢复
    现场。用于给不方便换成 TracedThread 的裸线程 / 回调补上下文。
    """
    ctx = contextvars.copy_context()

    def _wrapped(*args, **kwargs):
        return ctx.run(fn, *args, **kwargs)

    return _wrapped


class TracedThread(threading.Thread):
    """自动携带当前链路上下文的 Thread。

    构造时抓取当前线程的上下文快照，``run`` 时在工作线程恢复快照：
    任务看到的 correlation-id 与当前 span 与派发线程一致，线程内
    新建的 span 挂到派发时的当前 span 下。
    """

    def __init__(self, group=None, target=None, name=None, args=(), kwargs=None,
                 daemon=None):
        super().__init__(group=group, target=target, name=name,
                         args=args, kwargs=kwargs, daemon=daemon)
        self._trace_ctx = contextvars.copy_context()

    def run(self):
        if self._target is None:
            return
        self._trace_ctx.run(
            self._target, *self._args, **self._kwargs
        )


class TracedThreadPoolExecutor(ThreadPoolExecutor):
    """自动传播当前链路上下文的 ThreadPoolExecutor。

    每个提交任务在提交线程抓取上下文快照（``map`` 同样走 submit），
    工作线程内恢复快照执行；多个链路共用一个池也不会串号。
    """

    def submit(self, fn, /, *args, **kwargs):
        wrapped = wrap(fn)
        return super().submit(wrapped, *args, **kwargs)
