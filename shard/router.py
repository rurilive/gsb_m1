"""键到节点的路由实现。

目前只有取模路由（ModuloRouter）。集群扩缩容时它的迁移行为
见 demo.py 的统计输出。
"""

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
