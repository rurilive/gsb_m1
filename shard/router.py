"""键到节点的路由实现。

提供两种实现：
- ModuloRouter：hash(key) % N 的取模路由，N 变化时几乎全量迁移。
- ConsistentHashRouter：带虚拟节点的一致性哈希，增删节点只迁移
  必要的一小部分 key；虚拟节点数支持按整数权重放大并可随时调整。

集群扩缩容时两者的迁移行为对比见 demo.py 的统计输出。
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
    """带虚拟节点的一致性哈希路由。

    每个物理节点在环上占 virtual_nodes * weight 个虚拟节点；
    虚拟节点位置由 md5("{node}#{replica_index}") 决定，key 落到
    顺时针方向的第一个虚拟节点所属的物理节点上。增删节点或调整
    权重时，只有受影响环段内的 key 换归属。
    """

    def __init__(self, nodes, virtual_nodes=150, weights=None):
        if not isinstance(virtual_nodes, int) or virtual_nodes <= 0:
            raise ValueError("virtual_nodes must be a positive integer")
        self._virtual_nodes = virtual_nodes
        # node -> 当前权重（整数，>=1）
        self._weights = {}
        # 环：哈希位与归属物理节点按哈希位升序一一对应
        self._ring_hashes = []
        self._ring_nodes = []
        super().__init__(nodes)
        for node in list(self._nodes):
            self.set_weight(node, (weights or {}).get(node, 1))

    def add(self, node, weight=1):
        """上线一个节点。已存在时静默返回（改权重请用 set_weight）。"""
        if node in self._weights:
            return
        self.set_weight(node, weight)

    def remove(self, node):
        """下线一个节点，摘光它的全部虚拟节点。不存在时静默返回。"""
        if node not in self._weights:
            return
        for index in range(self._virtual_nodes * self._weights[node]):
            pos = bisect.bisect_left(self._ring_hashes,
                                    self._replica_hash(node, index))
            if pos < len(self._ring_hashes) and self._ring_nodes[pos] == node:
                self._ring_hashes.pop(pos)
                self._ring_nodes.pop(pos)
        del self._weights[node]
        self._nodes.remove(node)

    def set_weight(self, node, weight):
        """设置节点权重（正整数，可随时调整）。

        虚拟节点按 replica 下标顺序排布，权重变化时只增量增删
        下标区间内的虚拟节点，低编号虚拟节点的环位置保持不变。
        """
        if not isinstance(weight, int) or weight <= 0:
            raise ValueError("weight must be a positive integer")
        if node not in self._weights:
            if node not in self._nodes:
                self._nodes.append(node)
            current = 0
        else:
            current = self._virtual_nodes * self._weights[node]
        target = self._virtual_nodes * weight
        if target > current:
            for index in range(current, target):
                h = self._replica_hash(node, index)
                pos = bisect.bisect_left(self._ring_hashes, h)
                if pos < len(self._ring_hashes) and self._ring_hashes[pos] == h:
                    # 极小概率的哈希撞点：同一位只保留先到的节点
                    continue
                self._ring_hashes.insert(pos, h)
                self._ring_nodes.insert(pos, node)
        else:
            for index in range(target, current):
                h = self._replica_hash(node, index)
                pos = bisect.bisect_left(self._ring_hashes, h)
                if pos < len(self._ring_hashes) and self._ring_nodes[pos] == node:
                    self._ring_hashes.pop(pos)
                    self._ring_nodes.pop(pos)
        self._weights[node] = weight

    @property
    def weights(self):
        return dict(self._weights)

    def _replica_hash(self, node, index):
        return _hash(f"{node}#{index}")

    def route(self, key):
        if not self._ring_hashes:
            raise KeyError("route on empty node list")
        pos = bisect.bisect_right(self._ring_hashes, _hash(key))
        if pos == len(self._ring_hashes):
            pos = 0  # 越过环尾，回到第一个虚拟节点
        return self._ring_nodes[pos]
