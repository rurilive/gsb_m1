"""节点与新旧链表：缓存本体和单线程参考实现共用这一套结构。"""


class Node:
    """链表节点。淘汰后调 clear，把 key/value 和两个指针都断开。"""

    __slots__ = ("key", "value", "prev", "next")

    def __init__(self, key, value):
        self.key = key
        self.value = value
        self.prev = None
        self.next = None

    def clear(self):
        self.key = None
        self.value = None
        self.prev = None
        self.next = None

    def __repr__(self):
        return "Node(%r, %r)" % (self.key, self.value)


class OrderList:
    """按新旧排的双向链表：头最新，尾最旧。"""

    def __init__(self):
        self._head = None
        self._tail = None
        self._size = 0
        self._peak = 0

    def __len__(self):
        return self._size

    @property
    def head(self):
        return self._head

    @property
    def tail(self):
        return self._tail

    def push_front(self, node):
        """把节点挂到头部。"""
        node.prev = None
        node.next = self._head
        if self._head is not None:
            self._head.prev = node
        self._head = node
        if self._tail is None:
            self._tail = node
        self._size += 1
        if self._size > self._peak:
            self._peak = self._size

    def unlink(self, node):
        """把节点从链上摘掉，节点自己的两个指针也清干净。"""
        prev_node = node.prev
        next_node = node.next
        if prev_node is not None:
            prev_node.next = next_node
        elif self._head is node:
            self._head = next_node
        if next_node is not None:
            next_node.prev = prev_node
        elif self._tail is node:
            self._tail = prev_node
        node.prev = None
        node.next = None
        self._size -= 1

    def touch(self, node):
        """把节点挪到头部；本来就在头部就什么都不做。"""
        if self._head is node:
            return
        self.unlink(node)
        self.push_front(node)

    def pop_back(self):
        """摘掉最旧的节点并返回；链空了返回 None。"""
        node = self._tail
        if node is None:
            return None
        self.unlink(node)
        return node

    def nodes(self):
        """从头往尾遍历节点。

        步数按历史上见过的最大长度封顶，链子被写坏时也不会转不出来。
        """
        limit = self._peak + 8
        node = self._head
        while node is not None and limit > 0:
            yield node
            node = node.next
            limit -= 1
