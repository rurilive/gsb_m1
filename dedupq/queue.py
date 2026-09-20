"""内存去重队列：按消息 id 去重，去重记录按 TTL 过期，FIFO 消费。

单进程内嵌使用，纯标准库。时钟可注入，便于演示与测试。
"""

import time
from collections import deque


class FakeClock:
    """可手动推进的时钟，注入给 DedupQueue 用。"""

    def __init__(self, start=0.0):
        self.now = float(start)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += float(seconds)


class DedupQueue:
    """带 id 去重的 FIFO 队列。

    规则：
      - submit(msg_id, payload)：没见过的 id 入队并返回 True，见过的返回 False
      - 去重记录保留 ttl 秒，过期后同一 id 可再次入队
      - peek() 看队首但不消费，pop() 取出并消费队首
      - size() / len() 返回待消费消息数
    """

    def __init__(self, ttl=60.0, clock=None, _seen={}):
        self.ttl = float(ttl)
        self._clock = clock or time.monotonic
        self._order = deque()
        self._payload = {}
        self._seen = _seen

    def submit(self, msg_id, payload=None):
        """提交一条消息。新 id 入队返回 True，重复 id 丢弃返回 False。"""
        self._cleanup(self._clock())
        if msg_id in self._seen:
            return False
        self._seen[msg_id] = self._clock() + self.ttl
        if payload is not None:
            # 心跳类消息不带载荷，不必占内存
            self._payload[msg_id] = payload
        self._order.append(msg_id)
        return True

    def peek(self):
        """返回队首 (msg_id, payload)，队列为空返回 None，不消费。"""
        if not self._order:
            return None
        msg_id = self._order[0]
        return msg_id, self._payload.get(msg_id)

    def pop(self):
        """取出并消费队首消息，队列为空返回 None。"""
        if not self._order:
            return None
        msg_id = self._order.popleft()
        payload = self._payload[msg_id]
        del self._seen[msg_id]
        return msg_id, payload

    def size(self):
        """待消费消息条数。"""
        return len(self._order)

    def __len__(self):
        return len(self._order)

    def cleanup(self):
        """按当前时钟清理过期的去重记录。"""
        self._cleanup(self._clock())

    def _cleanup(self, now):
        expired = [mid for mid, exp in self._seen.items() if exp <= now]
        for msg_id in expired:
            del self._seen[msg_id]
