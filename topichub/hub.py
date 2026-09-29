"""topichub 的朴素一对一回调注册与直接调用（改造前的现状）。

现在只有一条投递路径：subscribe 把一个回调登记到主题上，publish 到
该主题时把登记过的回调挨个直接调用一遍，回调一返回就算送到。没有
通配主题、没有订阅谓词、没有确认与重投、没有重投队列、没有背压、
没有死信、没有注入时钟，也没有未确认消息的登记与退还。
多主题发布订阅、过滤、至少一次投递与确认、背压与退订见任务描述。
"""


class Message:
    """一条消息：主题、负载与全库单调递增的序号。

    seq 在 publish 时刻分配，从 1 开始，跨主题共用一个计数器。
    """

    __slots__ = ("topic", "payload", "seq")

    def __init__(self, topic, payload, seq):
        self.topic = topic
        self.payload = payload
        self.seq = seq

    def __repr__(self):
        return "Message(topic=%r, seq=%r, payload=%r)" % (
            self.topic,
            self.seq,
            self.payload,
        )


class Subscription:
    """subscribe() 返回的句柄：记录订阅用的主题与回调。"""

    __slots__ = ("topic", "handler", "active", "_hub")

    def __init__(self, topic, handler, hub):
        self.topic = topic
        self.handler = handler
        self.active = True
        self._hub = hub

    def unsubscribe(self):
        """退订，返回是否真的退掉了。"""
        return self._hub.unsubscribe(self)

    def __repr__(self):
        state = "active" if self.active else "closed"
        return "Subscription(topic=%r, %s)" % (self.topic, state)


class TopicHub:
    """最简单的主题订阅代理。

    - subscribe(topic, handler)：登记回调，返回一个 Subscription
    - unsubscribe(sub)：退订，已退过的返回 False
    - publish(topic, msg)：按主题取登记过的回调，挨个直接调用
    - 回调抛出的异常被吞掉并记入 errors，不影响其它回调
    - pending：当前未确认的在途消息条数（朴素实现里恒为 0）
    """

    def __init__(self):
        self._subs = {}
        self._seq = 0
        self.errors = []

    def subscribe(self, topic, handler):
        """登记一个回调到主题上，返回 Subscription 句柄。"""
        if not callable(handler):
            raise TypeError("handler must be callable")
        sub = Subscription(topic, handler, self)
        self._subs.setdefault(topic, []).append(sub)
        return sub

    def unsubscribe(self, sub):
        """退订，已退过或不属于本库的返回 False。"""
        if not sub.active:
            return False
        subs = self._subs.get(sub.topic)
        if not subs or sub not in subs:
            return False
        subs.remove(sub)
        sub.active = False
        return True

    def publish(self, topic, msg=None):
        """把消息按主题投给登记过的回调，返回消息序号。

        逐个直接调用回调，回调返回即算送达，没有任何确认或重投。
        """
        self._seq += 1
        message = Message(topic, msg, self._seq)
        for sub in list(self._subs.get(topic, [])):
            if not sub.active:
                continue
            try:
                sub.handler(message)
            except Exception as exc:  # 订阅者的异常不拖垮代理
                self.errors.append(exc)
        return message.seq

    def subscriber_count(self, topic):
        """取回某主题上仍然活跃的订阅数。"""
        return sum(1 for s in self._subs.get(topic, []) if s.active)

    def pending(self):
        """当前未确认的在途消息条数，朴素实现里没有确认，恒为 0。"""
        return 0
