"""idemretry：带幂等键与自动重试的提交客户端。

对外契约：

- ``submit(key, payload)``：首次受理执行一次 ``transport``，返回 ``Receipt``
- 幂等窗口（``ttl`` 秒）内用同一 ``key`` 再次提交，回放同一条回执，不重复执行
- ``transport`` 抛 ``TransientError`` 视为可重试，抛其他异常视为确定性失败
- 瞬时故障自动重试，最多 ``max_attempts`` 次尝试（含首次）

纯标准库，无外部依赖。时钟可注入，便于演示与测试。
"""

import time


class TransientError(Exception):
    """可重试的瞬时故障：网络抖动、下游限流等。"""


class PermanentError(Exception):
    """确定性故障：重试也不会变好，立即上抛。"""


class DuplicateKey(Exception):
    """同一个幂等键已有一条受理记录。"""


class RetryExhausted(Exception):
    """尝试次数用尽仍未成功。"""


class Receipt:
    """一次受理的凭据。``replayed`` 为真表示未真正执行、回放已有结果。"""

    __slots__ = ("key", "value", "attempts", "replayed")

    def __init__(self, key, value, attempts, replayed=False):
        self.key = key
        self.value = value
        self.attempts = attempts
        self.replayed = replayed

    def __repr__(self):
        return "Receipt(%r, %r, attempts=%d, replayed=%s)" % (
            self.key, self.value, self.attempts, self.replayed)


class IdempotentClient:
    """幂等提交客户端。

    ``transport(key, payload)`` 执行真正的副作用并返回结果；抛
    ``TransientError`` 表示这一次可以重来，抛其他异常表示确定性失败。
    """

    def __init__(self, transport, clock=None, ttl=60.0, max_attempts=3):
        self._transport = transport
        self._clock = clock or time.monotonic
        self._ttl = float(ttl)
        self._max_attempts = int(max_attempts)
        self._keys = {}     # key -> 幂等键到期时刻
        self._results = {}  # key -> (结果, 尝试次数, 到期时刻)
        self.calls = []     # transport 实际收到的每次 (key, payload)

    def submit(self, key, payload):
        """提交一笔业务，返回 Receipt。"""
        now = self._clock()
        self._expire(now)
        if key in self._results:
            value, attempts, _ = self._results[key]
            return Receipt(key, value, attempts=attempts, replayed=True)
        if key in self._keys:
            raise DuplicateKey(key)
        self._keys[key] = now + self._ttl
        try:
            value, attempts = self._attempt_loop(key, payload)
        except BaseException:
            # 本次受理没有产生确定结果，不能把键占住：
            # 否则调用方只能干等到幂等窗口到期才能用同键重发。
            self._keys.pop(key, None)
            raise
        self._results[key] = (value, attempts, now + self._ttl)
        return Receipt(key, value, attempts=attempts)

    def _attempt_loop(self, key, payload):
        """按 max_attempts 预算执行 transport，瞬时故障就重来。"""
        last = None
        for attempt in range(self._max_attempts):
            try:
                return self._send(key, payload), attempt + 1
            except TransientError as exc:
                last = exc
        raise RetryExhausted(key) from last

    def _send(self, key, payload):
        # 每次尝试都必须用同一个幂等键：下游按提交键去重，
        # 键一旦掺进尝试序号，超时后重试就会被当成新单，造成重复入账。
        self.calls.append((key, payload))
        return self._transport(key, payload)

    def _expire(self, now):
        """清掉已经到期的幂等键与结果缓存。"""
        for key in [k for k, exp in self._keys.items() if exp <= now]:
            del self._keys[key]
        for key in [k for k, (_, _, exp) in self._results.items() if exp <= now]:
            del self._results[key]
