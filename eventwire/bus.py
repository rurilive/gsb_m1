"""同步事件总线：订阅回调，发布即分发。

SyncBus 是整条链路的顺序参考实现：发布方按订阅顺序逐个调用处理器，
处理器什么时候返回，这次发布就算什么时候完。没有编号、没有重放，
也没有任何背压保护，某一个处理器慢，发布方和排在后面的订阅者都得等。
"""

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
