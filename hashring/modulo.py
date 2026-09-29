"""朴素取模分片的现有实现。

把所有节点排成一个列表，key 的哈希对节点个数取模得到下标，落到哪个
节点就归哪个节点。列表里每个物理节点只占一个位置，下标由当前位置决定。

取模分片有一个绕不开的毛病：分母一变就全盘重排。增加或删除一个节点，
节点个数随之改变，绝大多数 key 的取模结果都会变，归属跟着跳走；也无法
按节点能力分配权重，负载只能听天由命。
"""

import hashlib


def _hash(text):
    """把字符串映射成 64 位整数，取值稳定，便于跨进程复现。"""
    digest = hashlib.md5(text.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


class ModuloSharding:
    """按 key 哈希对节点个数取模来分片。

    节点顺序就是分片下标的顺序；lookup 返回 key 取模后命中的节点，
    空列表返回 None。nodes 返回排好序的节点名，仅供展示，不改变下标顺序。
    """

    def __init__(self, nodes=(), hash_fn=None):
        self._nodes = []
        self._hash = hash_fn or _hash
        for node in nodes:
            self.add_node(node)

    def add_node(self, node):
        """把一个节点追加到列表末尾。重复加入同一节点不产生新位置。"""
        if not isinstance(node, str) or not node:
            raise ValueError("node must be a non-empty string")
        if node in self._nodes:
            return
        self._nodes.append(node)

    def remove_node(self, node):
        """把一个节点从列表里摘掉；节点不存在时抛 KeyError。"""
        if node not in self._nodes:
            raise KeyError(node)
        self._nodes.remove(node)

    def lookup(self, key):
        """返回 key 归属的节点；空列表返回 None。"""
        if not self._nodes:
            return None
        index = self._hash(key) % len(self._nodes)
        return self._nodes[index]

    def nodes(self):
        """当前列表里的节点，按名字排序。"""
        return sorted(self._nodes)
