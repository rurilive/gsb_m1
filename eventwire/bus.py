"""同步事件总线：订阅回调，发布即分发。

SyncBus 是整条链路的顺序参考实现：发布方按订阅顺序逐个调用处理器，
处理器什么时候返回，这次发布就算什么时候完。没有编号、没有重放，
也没有任何背压保护，某一个处理器慢，发布方和排在后面的订阅者都得等。

OrderedBus 在另一条路上：每条事件拿一个单调递增的全序编号，先落 Journal
再异步分发；每个订阅者一条有界队列一个投递线程，慢订阅者只积压自己；
最近若干条事件留在内存窗口里，供新订阅者按编号补发。
"""

import queue
import threading
import time
from collections import deque

from eventwire.journal import Journal
from eventwire.topics import matches, split_pattern, split_topic


class SyncBus:
    """一张订阅表加同步分发，分发顺序就是订阅顺序。"""

    def __init__(self):
        self._subscribers = {}

    def subscribe(self, name, handler, pattern="**"):
        """登记一个订阅，返回是不是新名字。

        名字重复时替换处理器和模式，位置保持第一次订阅时的先后。
        处理器签名是 handler(topic, payload)。
        """
        if not isinstance(name, str) or not name:
            raise ValueError("订阅名必须是非空 str")
        if not callable(handler):
            raise TypeError(f"handler 必须可调用，收到 {type(handler).__name__}")
        split_pattern(pattern)  # 模式不合法当场报错
        is_new = name not in self._subscribers
        self._subscribers[name] = (pattern, handler)
        return is_new

    def unsubscribe(self, name):
        """删掉一个订阅，删掉了返回 True，本来就没有返回 False。"""
        return self._subscribers.pop(name, None) is not None

    def subscriber_names(self):
        """全部订阅名，按订阅顺序。"""
        return tuple(self._subscribers)

    def publish(self, topic, payload):
        """按订阅顺序同步调用所有匹配的处理器，返回调用了几家。

        分发开始时取一次订阅表快照，处理器里改订阅不影响这一趟。
        某个处理器抛异常，其余订阅者照样叫完，全部结束再抛第一个异常。
        """
        split_topic(topic)  # 主题不合法当场报错，跟有没有订阅者无关
        failures = []
        delivered = 0
        for pattern, handler in tuple(self._subscribers.values()):
            if not matches(pattern, topic):
                continue
            delivered += 1
            try:
                handler(topic, payload)
            except Exception as failure:
                failures.append(failure)
        if failures:
            raise failures[0]
        return delivered


class WindowExpired(Exception):
    """订阅者要补的旧事件已经滚出窗口，不允许静默跳过。"""


_STOP = object()  # 断开订阅者时塞进队列让投递线程退出的哨兵


class _Subscription:
    """一个订阅者的运行状态：有界队列、投递线程和计数器。"""

    __slots__ = ("name", "pattern", "handler", "queue", "stop",
                 "delivered", "dropped", "errors", "state", "thread")

    def __init__(self, name, pattern, handler, backlog):
        self.name = name
        self.pattern = pattern
        self.handler = handler
        self.queue = queue.Queue(maxsize=backlog)
        self.stop = threading.Event()
        self.delivered = 0
        self.dropped = 0
        self.errors = 0
        self.state = "live"  # live / disconnected
        self.thread = None


class OrderedBus:
    """带全序编号、落盘重放和背压保护的事件总线。

    publish 给每条事件发单调递增的全序编号，先落 Journal 再分发；上游按
    编号重投时，同号或更老的编号幂等丢弃。每个订阅者有独立的有界队列和
    投递线程，慢订阅者只积压自己，积压超限按 overflow 处置："drop" 丢新
    事件并计数，"disconnect" 断开该订阅者。最近 window 条事件留在内存
    窗口里供 subscribe(since=...) 补发，更老的编号抛 WindowExpired。
    进程重启后用同一个路径重开，编号接着水位走，不重发也不跳号。
    """

    def __init__(self, path, window=256, backlog=64, overflow="drop"):
        for label, value in (("window", window), ("backlog", backlog)):
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{label} 必须是正整数，收到 {value!r}")
        if overflow not in ("drop", "disconnect"):
            raise ValueError(
                f"overflow 只能是 'drop' 或 'disconnect'，收到 {overflow!r}")
        self._window = window
        self._backlog = backlog
        self._overflow = overflow
        self._journal = Journal(path)
        self._lock = threading.Lock()
        self._events = deque()  # 窗口内的 (seq, topic, payload)，按编号升序
        self._high = 0
        self._subscribers = {}
        self._closed = False
        self._recover()

    def _recover(self):
        """从 Journal 恢复水位和窗口，同号记录只算第一次。"""
        for record in self._journal.read():
            seq = record.get("seq")
            topic = record.get("topic")
            if (not isinstance(seq, int) or isinstance(seq, bool) or seq < 1
                    or not isinstance(topic, str) or "payload" not in record):
                raise ValueError(
                    f"日志里有不是事件的记录: {str(record)[:40]!r}")
            split_topic(topic)
            if seq <= self._high:
                continue
            self._high = seq
            self._events.append((seq, topic, record["payload"]))
            while len(self._events) > self._window:
                self._events.popleft()

    def _window_low(self):
        """窗口里最小的编号，窗口空时是下一个要发的编号。"""
        return self._events[0][0] if self._events else self._high + 1

    def publish(self, topic, payload, seq=None):
        """发布一条事件，返回它的全序编号。

        seq 为 None 时由总线发号（水位加一）；上游自带编号重投时传 seq，
        同号或更老的编号幂等丢弃、返回该编号但不再落盘不再分发。先落盘
        再分发，落盘失败（比如 payload 没法 JSON 序列化）不占编号。
        """
        split_topic(topic)  # 主题不合法当场报错
        if seq is not None and (not isinstance(seq, int)
                                or isinstance(seq, bool) or seq < 1):
            raise ValueError(f"seq 必须是正 int 或 None，收到 {seq!r}")
        with self._lock:
            if self._closed:
                raise ValueError("OrderedBus 已经关掉了，不能继续发布")
            if seq is None:
                seq = self._high + 1
            elif seq <= self._high:
                return seq  # 同号或更老的重投，幂等丢弃
            self._journal.append(
                {"seq": seq, "topic": topic, "payload": payload})
            self._high = seq
            self._events.append((seq, topic, payload))
            while len(self._events) > self._window:
                self._events.popleft()
            for sub in tuple(self._subscribers.values()):
                if matches(sub.pattern, topic):
                    self._enqueue(sub, (topic, payload))
        return seq

    def subscribe(self, name, handler, pattern="**", since=None):
        """登记一个订阅，返回是不是新名字。

        since 为 None 时只收之后的新事件；否则先把窗口内编号大于 since
        的旧事件按序同步补发给 handler，再转异步接收新事件。since 老到
        要补的事件已经滚出窗口时抛 WindowExpired，不静默跳过。同名重复
        订阅替换处理器与模式，旧投递线程停掉。
        """
        if not isinstance(name, str) or not name:
            raise ValueError("订阅名必须是非空 str")
        if not callable(handler):
            raise TypeError(f"handler 必须可调用，收到 {type(handler).__name__}")
        split_pattern(pattern)  # 模式不合法当场报错
        if since is not None and (not isinstance(since, int)
                                  or isinstance(since, bool) or since < 0):
            raise ValueError(f"since 必须是非负 int 或 None，收到 {since!r}")
        with self._lock:
            if self._closed:
                raise ValueError("OrderedBus 已经关掉了，不能继续订阅")
            low = self._window_low()
            if since is not None and since < low - 1:
                raise WindowExpired(
                    f"编号 {since + 1} 起的事件已滚出窗口"
                    f"（窗口下限 {low}），不允许静默跳过")
            replay = [event for event in self._events
                      if since is not None and event[0] > since]
            old = self._subscribers.get(name)
            is_new = old is None
            sub = _Subscription(name, pattern, handler, self._backlog)
            self._subscribers[name] = sub
        if old is not None:
            self._stop_sub(old)
        # 补发在锁外同步做：期间发布的新事件进队列，等投递线程起来后
        # 按序跟上，不会插到补发前头。
        for seq, topic, payload in replay:
            if not matches(pattern, topic):
                continue
            try:
                handler(topic, payload)
            except Exception:
                sub.errors += 1
            else:
                sub.delivered += 1
        thread = threading.Thread(target=self._run, args=(sub,),
                                  name=f"eventwire-ordered-{name}",
                                  daemon=True)
        sub.thread = thread
        thread.start()
        return is_new

    def unsubscribe(self, name):
        """删掉一个订阅并停掉它的投递线程，删掉了返回 True。"""
        with self._lock:
            sub = self._subscribers.pop(name, None)
        if sub is None:
            return False
        self._stop_sub(sub)
        return True

    def subscriber_names(self):
        """全部订阅名，按订阅顺序。"""
        with self._lock:
            return tuple(self._subscribers)

    def flush(self, timeout=None):
        """等到所有存活订阅者的积压清空，超时返回 False。"""
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            with self._lock:
                subs = [sub for sub in self._subscribers.values()
                        if sub.state == "live"]
            if all(sub.queue.unfinished_tasks == 0 for sub in subs):
                return True
            if deadline is not None and time.monotonic() >= deadline:
                return False
            time.sleep(0.005)

    def stats(self):
        """水位、窗口下限，以及每个订阅者的投递、丢弃、错误、积压和状态。"""
        with self._lock:
            return {
                "high_water": self._high,
                "window_low": self._window_low(),
                "window_size": len(self._events),
                "subscribers": {
                    name: {
                        "state": sub.state,
                        "delivered": sub.delivered,
                        "dropped": sub.dropped,
                        "errors": sub.errors,
                        "pending": sub.queue.qsize(),
                    }
                    for name, sub in self._subscribers.items()
                },
            }

    def close(self):
        """停掉所有投递线程并关掉 Journal，可重复调用。"""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            subs = tuple(self._subscribers.values())
        for sub in subs:
            self._stop_sub(sub)
        self._journal.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False

    def _enqueue(self, sub, item):
        """非阻塞进队，超限按 overflow 丢并计数或断开。"""
        if sub.state != "live":
            sub.dropped += 1
            return
        try:
            sub.queue.put_nowait(item)
        except queue.Full:
            sub.dropped += 1
            if self._overflow == "disconnect":
                sub.state = "disconnected"
                while True:
                    try:
                        sub.queue.get_nowait()
                        sub.queue.task_done()
                    except queue.Empty:
                        break
                sub.queue.put_nowait(_STOP)

    @staticmethod
    def _run(sub):
        """投递线程：从自己的队列取事件调处理器，异常计数不中断。"""
        while not sub.stop.is_set():
            try:
                item = sub.queue.get(timeout=0.05)
            except queue.Empty:
                continue
            if item is _STOP:
                sub.queue.task_done()
                return
            topic, payload = item
            try:
                sub.handler(topic, payload)
            except Exception:
                sub.errors += 1
            else:
                sub.delivered += 1
            sub.queue.task_done()

    @staticmethod
    def _stop_sub(sub):
        sub.stop.set()
        if sub.thread is not None:
            sub.thread.join()
