"""内存发布订阅：按主题订阅，publish 把消息投递给该主题全部订阅者。

当前实现只用内存字典装订阅关系，投递时逐个调用订阅者回调，回调抛出的
异常被吞掉记日志；没有确认、重投、过滤、背压与回放，投完即算完。
"""

import logging
import threading

logger = logging.getLogger(__name__)


class Message:
    """一条消息：主题、负载与单调递增的序号。

    seq 在 publish 时刻由总线分配，同一主题内严格递增，从 1 开始。
    """

    __slots__ = ("topic", "payload", "seq")

    def __init__(self, topic, payload, seq):
        self.topic = topic
        self.payload = payload
        self.seq = seq

    def __repr__(self):
        return f"Message(topic={self.topic!r}, seq={self.seq!r}, payload={self.payload!r})"


class Subscription:
    """subscribe() 返回的句柄：记录订阅用的回调与主题。"""

    __slots__ = ("topic", "callback", "active", "_bus")

    def __init__(self, topic, callback, bus):
        self.topic = topic
        self.callback = callback
        self.active = True
        self._bus = bus

    def unsubscribe(self):
        return self._bus.unsubscribe(self)

    def __repr__(self):
        state = "active" if self.active else "closed"
        return f"Subscription(topic={self.topic!r}, {state})"


class MessageBus:
    """最简单的内存发布订阅。

    - subscribe(topic, callback)：订阅主题，回调收一个 Message
    - unsubscribe(sub)：取消订阅，已取消的返回 False
    - publish(topic, payload)：给该主题全部活跃订阅者投递一条消息，返回消息序号
    - 订阅回调抛出的异常被吞掉并记入 errors，不影响其它订阅者
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._subs = {}
        self._seq = {}
        self.errors = []

    def subscribe(self, topic, callback):
        if not callable(callback):
            raise TypeError("callback must be callable")
        with self._lock:
            sub = Subscription(topic, callback, self)
            self._subs.setdefault(topic, []).append(sub)
            return sub

    def unsubscribe(self, sub):
        with self._lock:
            if not sub.active:
                return False
            subs = self._subs.get(sub.topic)
            if not subs or sub not in subs:
                return False
            subs.remove(sub)
            sub.active = False
            return True

    def publish(self, topic, payload=None):
        with self._lock:
            seq = self._seq.get(topic, 0) + 1
            self._seq[topic] = seq
            msg = Message(topic, payload, seq)
            subs = list(self._subs.get(topic, []))
        for sub in subs:
            if not sub.active:
                continue
            try:
                sub.callback(msg)
            except Exception as exc:  # 订阅者的异常不拖垮总线
                logger.warning("subscriber error on %r: %r", topic, exc)
                self.errors.append(exc)
        return seq

    def subscriber_count(self, topic):
        with self._lock:
            return sum(1 for s in self._subs.get(topic, []) if s.active)