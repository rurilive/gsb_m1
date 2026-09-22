"""可注入的假解析上游。

顶替真实的权威 DNS 或内网解析服务：内存里放一份 zone，
按 name 查地址和 TTL，查不到或标了失败就抛 UpstreamError。
测试和演示里靠它的计数器统计上游被打了几次。
"""

import threading
import time


class UpstreamError(Exception):
    """解析失败，跟真实解析服务超时/查不到时的对外契约一致。"""


class Answer:
    """一次解析应答。

    name: 被查询的域名。
    address: 解析出的地址。
    ttl: 上游给的有效期秒数；None 表示上游没给。
    """

    __slots__ = ("name", "address", "ttl")

    def __init__(self, name, address, ttl):
        self.name = name
        self.address = address
        self.ttl = ttl

    def __repr__(self):
        return "Answer(name=%r, address=%r, ttl=%r)" % (
            self.name, self.address, self.ttl)

    def __eq__(self, other):
        if not isinstance(other, Answer):
            return NotImplemented
        return (self.name, self.address, self.ttl) == (
            other.name, other.address, other.ttl)


class FakeUpstream:
    """内存解析服务。

    zone: name -> (address, ttl) 的映射，ttl 可以是 None。
    delay: 每次解析的模拟耗时秒数，默认 0，用来把并发窗口拉大。
    """

    def __init__(self, zone=None, delay=0.0):
        self._lock = threading.Lock()
        self._zone = dict(zone or {})
        self._delay = float(delay)
        self._failing = set()
        self._calls = 0
        self._calls_by_name = {}
        self._in_flight = 0
        self._peak_in_flight = 0

    def resolve(self, name):
        """解析一个域名，返回 Answer；查不到或标了失败抛 UpstreamError。"""
        with self._lock:
            self._calls += 1
            self._calls_by_name[name] = self._calls_by_name.get(name, 0) + 1
            self._in_flight += 1
            if self._in_flight > self._peak_in_flight:
                self._peak_in_flight = self._in_flight
            failing = name in self._failing
            record = self._zone.get(name)
        try:
            if self._delay:
                time.sleep(self._delay)
            if failing or record is None:
                raise UpstreamError("upstream resolve failed: %s" % name)
            address, ttl = record
            return Answer(name, address, ttl)
        finally:
            with self._lock:
                self._in_flight -= 1

    def set_record(self, name, address, ttl):
        """写入或更新一条记录，同时清掉它的失败标记。"""
        with self._lock:
            self._zone[name] = (address, ttl)
            self._failing.discard(name)

    def set_failing(self, name, failing=True):
        """给某个域名标上或撤掉失败标记，模拟上游抖动。"""
        with self._lock:
            if failing:
                self._failing.add(name)
            else:
                self._failing.discard(name)

    def calls_for(self, name):
        """某个域名被打过几次。"""
        with self._lock:
            return self._calls_by_name.get(name, 0)

    def stats(self):
        """计数快照，返回独立 dict，调用方随便改。"""
        with self._lock:
            return {
                "calls": self._calls,
                "peak_in_flight": self._peak_in_flight,
            }
