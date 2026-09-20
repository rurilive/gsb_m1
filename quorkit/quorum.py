"""按多数派选主的法定人数小工具。

集群成员由外部注入的 MemberTable 描述（测试里借它模拟节点的加入、
离开与失联），所有时刻都来自构造时传入的 clock；纯标准库，不碰
真实时间，也不用真等。

一个 Quorum 实例代表一个节点：它记下自己收到的心跳、维护自己的
任期号，并按当前在册成员里的活跃多数派判断自己能不能当 leader。
"""

import threading
import time


class MemberTable:
    """在册成员表。

    由外部持有，可以同时注入给多个节点，用来模拟真实集群里各节点
    看到的成员视图。节点的加入和离开都记在这里。
    """

    def __init__(self, nodes=()):
        self._lock = threading.Lock()
        self._members = set(nodes)

    def add(self, node):
        """把节点加进在册成员。"""
        with self._lock:
            self._members.add(node)

    def remove(self, node):
        """把节点从在册成员里摘掉；不在册时静默忽略。"""
        with self._lock:
            self._members.discard(node)

    def nodes(self):
        """当前在册成员的快照。"""
        with self._lock:
            return set(self._members)

    def __len__(self):
        with self._lock:
            return len(self._members)

    def __contains__(self, node):
        with self._lock:
            return node in self._members


class Quorum:
    """单个节点的法定人数判定器。

    cluster: 注入的 MemberTable，多个节点可以共享同一份。
    clock:   返回当前时刻的可调用对象，默认 time.monotonic，测试可注入。
    timeout: 本节点配置的失联超时，单位秒。
    config:  集群商量好的公共配置，例如 {"heartbeat_timeout": 5.0}；
             只要协商过，各节点就该以它为准。

    内部一把锁保护，单个方法调用对多线程安全。
    """

    def __init__(self, cluster, clock=time.monotonic, timeout=1.0, config=None):
        if timeout <= 0:
            raise ValueError("timeout must be > 0")
        self._cluster = cluster
        self._clock = clock
        self._timeout = timeout
        self._config = config or {}
        self._term = 0
        self._seen = {}                                # node -> 最近一次心跳时刻
        self._lock = threading.Lock()

    def majority(self):
        """凑够这么多票才算多数派。

        按当前在册成员动态计算（N//2 + 1），成员扩容或摘除后立刻生效，
        不能沿用构造时的旧成员数。
        """
        return len(self._cluster) // 2 + 1

    def negotiated_timeout(self):
        """集群协商出来的失联超时；没协商过就退回本地配置。"""
        return self._config.get("heartbeat_timeout", self._timeout)

    def heartbeat(self, node, ts, term=0):
        """记下 node 在 ts 时刻的心跳，它在这条心跳里声称自己处于 term 任期。

        返回这条心跳是否被采纳。以下心跳一律不认：

        - 来自不在册成员（已被摘除）的心跳，摘了就不能再参与计票；
        - term 落后于本节点当前任期的心跳，旧任期的消息不能复活旧 leader；

        term 比本节点更新时，先把本节点任期跟到该 term 再记为活跃，
        任期号只许往前、不许回退。
        """
        with self._lock:
            if node not in self._cluster:
                return False
            if term < self._term:
                return False
            if term > self._term:
                self._term = term
            self._seen[node] = ts
            return True

    def term(self):
        """本节点目前的任期号，初始为 0。"""
        with self._lock:
            return self._term

    def active(self):
        """此刻还活着的节点集合，返回独立快照。"""
        with self._lock:
            return self._active(self._clock())

    def elect(self):
        """按多数派把自己选成 leader。

        票够就任期加一、当上 leader 并返回新任期；票不够返回 None。
        """
        with self._lock:
            self._term += 1
            if len(self._active(self._clock())) >= self.majority():
                return self._term
            return None

    def _active(self, now):
        """此刻还活着的在册节点。调用方必须持锁。

        活跃判定走集群协商好的超时（没协商过才退回本机配置），并且只看
        当前在册成员：被摘除的节点即使留着旧心跳时间戳也不参与计票。
        """
        timeout = self.negotiated_timeout()
        return {
            node
            for node, ts in self._seen.items()
            if node in self._cluster and now - ts < timeout
        }
