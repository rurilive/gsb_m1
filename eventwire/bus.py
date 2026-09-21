"""同步事件总线：订阅回调，发布即分发。

SyncBus 是整条链路的顺序参考实现：发布方按订阅顺序逐个调用处理器，
处理器什么时候返回，这次发布就算什么时候完。没有编号、没有重放，
也没有任何背压保护，某一个处理器慢，发布方和排在后面的订阅者都得等。
"""

import collections
import threading
import time

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
    """since 指到的老编号已经滚出重放窗口，补不齐了，不许静默跳过。"""


class _Subscription:
    """一个订阅者的异步投递通道：有界队列加一条专属工作线程。

    队列里先是订阅时预装的补发事件，再是之后的实时事件，工作线程
    严格按入队顺序逐个调用处理器，慢只慢自己，不碰发布方和别人。
    """

    def __init__(self, name, handler, pattern, backlog, overflow, replay):
        self.name = name
        self.handler = handler
        self.pattern = pattern
        self._backlog = backlog
        self._overflow = overflow
        self._cond = threading.Condition()
        self._queue = collections.deque(replay)
        self._active = 0
        self._accepting = True
        self.delivered = 0
        self.dropped = 0
        self.errors = 0
        self.state = "live"  # live / disconnected / closed
        self._thread = threading.Thread(
            target=self._run, name=f"eventwire-{name}", daemon=True)

    def start(self):
        self._thread.start()

    def update(self, handler, pattern, replay):
        """同名重订阅：换处理器和模式，补发事件插到积压前面，位置不动。"""
        with self._cond:
            self.handler = handler
            self.pattern = pattern
            self._queue.extendleft(reversed(replay))
            self._cond.notify()

    def enqueue(self, record):
        """塞一条事件，超限按 overflow 丢并计数或直接断开。"""
        with self._cond:
            if self.state != "live" or not self._accepting:
                self.dropped += 1
                return
            if len(self._queue) >= self._backlog:
                self.dropped += 1
                if self._overflow == "disconnect":
                    self.state = "disconnected"
                    self._queue.clear()
                self._cond.notify_all()
                return
            self._queue.append(record)
            self._cond.notify()

    def _run(self):
        while True:
            with self._cond:
                while (not self._queue and self._accepting
                       and self.state == "live"):
                    self._cond.wait()
                if self.state != "live":
                    self._queue.clear()
                    return
                if not self._queue:
                    return  # 退订或关闭：在途事件送完再走人
                record = self._queue.popleft()
                self._active += 1
            try:
                self.handler(record["topic"], record["payload"])
            except Exception:
                with self._cond:
                    self.errors += 1
                    self._active -= 1
                    self._cond.notify_all()
            else:
                with self._cond:
                    self.delivered += 1
                    self._active -= 1
                    self._cond.notify_all()

    @property
    def idle(self):
        with self._cond:
            return not self._queue and not self._active

    def snapshot(self):
        with self._cond:
            return {
                "delivered": self.delivered,
                "dropped": self.dropped,
                "errors": self.errors,
                "pending": len(self._queue),
                "state": self.state,
            }

    def close(self):
        with self._cond:
            self._accepting = False
            self._cond.notify_all()
        self._thread.join()


class OrderedBus:
    """带全序编号、落盘重放与背压保护的事件总线。

    publish 给每条事件一个从 1 起单调递增的全序编号，先落 Journal 再
    异步分发给各订阅者；同一个编号再投一次被幂等丢掉，跳号直接报错。
    订阅者各自一条有界队列加工作线程，慢订阅者只积压自己，超限按
    overflow 丢并计数（"drop"）或断开（"disconnect"）。
    重开同一个文件时编号接着水位走，窗口内历史可按 since 重放。
    """

    def __init__(self, path, window=256, backlog=64, overflow="drop"):
        if not isinstance(window, int) or isinstance(window, bool) or window < 1:
            raise ValueError(f"window 必须是正整数，收到 {window!r}")
        if not isinstance(backlog, int) or isinstance(backlog, bool) or backlog < 1:
            raise ValueError(f"backlog 必须是正整数，收到 {backlog!r}")
        if overflow not in ("drop", "disconnect"):
            raise ValueError(f"overflow 只能是 'drop' 或 'disconnect'，收到 {overflow!r}")
        self._journal = Journal(path)
        self._window_size = window
        self._backlog = backlog
        self._overflow = overflow
        self._lock = threading.Lock()
        self._subscribers = {}
        self._window = collections.deque()
        self._next_seq = 1
        self._duplicates = 0
        self._closed = False
        for record in self._journal.read():
            seq = record.get("seq")
            if not isinstance(seq, int) or isinstance(seq, bool) or seq < 1:
                raise ValueError(f"Journal 里的记录没有合法 seq: {record!r}")
            if seq >= self._next_seq:
                self._next_seq = seq + 1
            self._window.append(record)
            while len(self._window) > self._window_size:
                self._window.popleft()

    def publish(self, topic, payload, seq=None):
        """发布一条事件，返回它的全序编号。

        seq 不给就用水位编号；给了且小于水位说明是同号重投，落盘与
        分发都跳过、计数后返回该编号；给了且大于水位是跳号，报
        ValueError。payload 必须能被 json 序列化，否则落盘报错。
        """
        split_topic(topic)  # 主题不合法当场报错，跟有没有订阅者无关
        with self._lock:
            if self._closed:
                raise ValueError("OrderedBus 已经关掉了，不能继续发布")
            if seq is None:
                seq = self._next_seq
            elif not isinstance(seq, int) or isinstance(seq, bool) or seq < 1:
                raise ValueError(f"seq 必须是正整数，收到 {seq!r}")
            if seq < self._next_seq:
                self._duplicates += 1
                return seq
            if seq > self._next_seq:
                raise ValueError(
                    f"编号不许跳：水位在 {self._next_seq}，收到 {seq}")
            record = {"seq": seq, "topic": topic, "payload": payload}
            self._journal.append(record)
            self._window.append(record)
            while len(self._window) > self._window_size:
                self._window.popleft()
            self._next_seq += 1
            for sub in tuple(self._subscribers.values()):
                if matches(sub.pattern, topic):
                    sub.enqueue(record)
            return seq

    def subscribe(self, name, handler, pattern="**", since=None):
        """登记一个订阅，返回是不是新名字。

        since 给了就先把窗口内编号大于 since 的旧事件按序补发，再转
        异步接收实时事件；since 太老、要补的编号已经滚出窗口时抛
        WindowExpired，不静默跳过。since 不给就只收实时事件。
        同名重复订阅替换处理器与模式、位置保持第一次订阅时的先后，
        已在途的积压事件照样送完。
        """
        if not isinstance(name, str) or not name:
            raise ValueError("订阅名必须是非空 str")
        if not callable(handler):
            raise TypeError(f"handler 必须可调用，收到 {type(handler).__name__}")
        split_pattern(pattern)  # 模式不合法当场报错
        if since is not None and (
                not isinstance(since, int) or isinstance(since, bool) or since < 0):
            raise ValueError(f"since 必须是非负整数或 None，收到 {since!r}")
        with self._lock:
            if self._closed:
                raise ValueError("OrderedBus 已经关掉了，不能继续订阅")
            floor = self._window[0]["seq"] if self._window else self._next_seq
            if since is not None and since < floor - 1:
                raise WindowExpired(
                    f"since={since} 太老，窗口下限是 {floor}，中间的事件补不齐")
            replay = [] if since is None else [
                record for record in self._window
                if record["seq"] > since and matches(pattern, record["topic"])]
            old = self._subscribers.get(name)
            if old is not None:
                old.update(handler, pattern, replay)
                return False
            sub = _Subscription(
                name, handler, pattern, self._backlog, self._overflow, replay)
            self._subscribers[name] = sub
        sub.start()
        return True

    def unsubscribe(self, name):
        """删掉一个订阅，删掉了返回 True，本来就没有返回 False。"""
        with self._lock:
            sub = self._subscribers.pop(name, None)
        if sub is None:
            return False
        sub.close()
        return True

    def subscriber_names(self):
        """全部订阅名，按订阅顺序。"""
        with self._lock:
            return tuple(self._subscribers)

    def stats(self):
        """水位、窗口下限与每个订阅者的投递、丢弃、积压和状态。"""
        with self._lock:
            return {
                "watermark": self._next_seq - 1,
                "window_floor": self._window[0]["seq"] if self._window else None,
                "window": len(self._window),
                "duplicates": self._duplicates,
                "subscribers": {
                    name: sub.snapshot()
                    for name, sub in self._subscribers.items()
                },
            }

    def wait_idle(self, timeout=5.0):
        """等到所有订阅者队列清空、手头事件处理完，超时返回 False。"""
        deadline = time.monotonic() + timeout
        while True:
            with self._lock:
                subs = tuple(self._subscribers.values())
            if all(sub.idle for sub in subs):
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.001)

    def close(self):
        """停掉全部订阅线程并关掉 Journal，可重复调用。"""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            subs = tuple(self._subscribers.values())
            self._subscribers.clear()
        for sub in subs:
            sub.close()
        self._journal.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False
