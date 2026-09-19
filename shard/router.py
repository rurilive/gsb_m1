"""键到节点的路由实现。

目前只有取模路由（ModuloRouter）。集群扩缩容时它的迁移行为
见 demo.py 的统计输出。
"""

import bisect
import hashlib


class Router:
    """路由接口：把一个 key 映射到某个节点名。

    节点名是任意可哈希字符串（生产里是 host:port）。
    """

    def __init__(self, nodes):
        # 保留首次传入顺序；重复节点名视为同一个
        self._nodes = []
        for n in nodes:
            if n not in self._nodes:
                self._nodes.append(n)

    @property
    def nodes(self):
        # 返回副本，调用方改不了内部状态
        return list(self._nodes)

    def add(self, node):
        """上线一个节点。已存在时静默返回。"""
        if node not in self._nodes:
            self._nodes.append(node)

    def remove(self, node):
        """下线一个节点。不存在时静默返回。"""
        if node in self._nodes:
            self._nodes.remove(node)

    def route(self, key):
        raise NotImplementedError


def _hash(key):
    """稳定的 key 哈希（md5 取整，跨进程可复现）。"""
    return int(hashlib.md5(str(key).encode("utf-8")).hexdigest(), 16)


class ModuloRouter(Router):
    """hash(key) % N 的取模路由。

    实现简单、分布均匀，但 N 变化时几乎所有 key 都会换归属，
    这正是集群扩缩容时缓存被打穿的根源。
    """

    def route(self, key):
        if not self._nodes:
            raise KeyError("route on empty node list")
        return self._nodes[_hash(key) % len(self._nodes)]


class ConsistentHashRouter(Router):
    """一致性哈希路由。

    每个物理节点按权重展开为若干个虚拟节点（默认 150 个/权重 1），
    散列到环上；key 沿环顺时针落到第一个虚拟节点所属的物理节点。
    增删节点只影响环上相邻区间的 key，其余 key 归属不变。
    """

    def __init__(self, nodes, replicas=150):
        super().__init__(nodes)
        self._replicas = replicas
        self._weights = {}
        self._points = []  # 环上所有虚拟节点的哈希值，升序
        self._owners = []  # 与 _points 对齐的物理节点名
        self._rebuild()

    def set_weight(self, node, weight):
        """调整节点权重（正整数），权重 2 的节点虚拟节点数翻倍。"""
        if not isinstance(weight, int) or isinstance(weight, bool) or weight < 1:
            raise ValueError("weight must be a positive integer")
        self._weights[node] = weight
        self._rebuild()

    def add(self, node):
        super().add(node)
        self._rebuild()

    def remove(self, node):
        super().remove(node)
        self._rebuild()

    def _rebuild(self):
        points = []
        for node in self._nodes:
            vnodes = self._replicas * self._weights.get(node, 1)
            for i in range(vnodes):
                points.append((_hash(f"{node}#{i}"), node))
        points.sort()
        self._points = [h for h, _ in points]
        self._owners = [n for _, n in points]

    def route(self, key):
        if not self._points:
            raise KeyError("route on empty node list")
        idx = bisect.bisect_right(self._points, _hash(key))
        if idx == len(self._points):
            idx = 0  # 越过环尾，绕回起点
        return self._owners[idx]
