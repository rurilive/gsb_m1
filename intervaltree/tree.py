"""闭区间集合：按 start 组织的增强二叉搜索树。

每个节点维护子树内最大的 end（max_end），查询时用于剪枝。
语义约定见 README，本文件与 README 如有出入，以 README 为准。
"""

from .errors import OverlapError


class _Node:
    __slots__ = ("start", "end", "max_end", "left", "right")

    def __init__(self, start, end):
        self.start = start
        self.end = end
        self.max_end = end
        self.left = None
        self.right = None


class IntervalTree:
    """闭区间集合，树中任意两个区间不重叠。"""

    def __init__(self):
        self._root = None
        self._size = 0

    def __len__(self):
        return self._size

    def insert(self, start, end):
        """插入闭区间 [start, end]。"""
        if start > end:
            raise ValueError("start must be <= end")
        if self._has_overlap(self._root, start, end):
            raise OverlapError("[%s, %s] overlaps existing interval" % (start, end))
        self._root = self._insert(self._root, start, end)
        self._size += 1

    def remove(self, start, end):
        """删除指定区间。"""
        self._root = self._delete(self._root, start, end)
        self._size -= 1

    def query_range(self, lo, hi):
        """返回与 [lo, hi] 相交的区间列表，按 start 升序。"""
        if lo > hi:
            raise ValueError("lo must be <= hi")
        out = []
        self._collect_range(self._root, lo, hi, out)
        return out

    def point_query(self, x):
        """返回覆盖点 x 的区间列表，按 start 升序。"""
        out = []
        self._collect_point(self._root, x, out)
        return out

    def _pull_up(self, node):
        node.max_end = node.end
        if node.left is not None:
            node.max_end = max(node.max_end, node.left.max_end)
        if node.right is not None:
            node.max_end = max(node.max_end, node.right.max_end)

    def _has_overlap(self, node, start, end):
        if node is None:
            return False
        if node.max_end < start:
            return False
        if self._has_overlap(node.left, start, end):
            return True
        if node.start < end and node.end > start:
            return True
        if node.start <= end:
            return self._has_overlap(node.right, start, end)
        return False

    def _insert(self, node, start, end):
        if node is None:
            return _Node(start, end)
        if (start, end) < (node.start, node.end):
            node.left = self._insert(node.left, start, end)
        else:
            node.right = self._insert(node.right, start, end)
        self._pull_up(node)
        return node

    def _delete(self, node, start, end):
        if node is None:
            return None
        if (start, end) < (node.start, node.end):
            node.left = self._delete(node.left, start, end)
        elif (start, end) > (node.start, node.end):
            node.right = self._delete(node.right, start, end)
        else:
            if node.left is None:
                return node.right
            if node.right is None:
                return node.left
            succ = node.right
            while succ.left is not None:
                succ = succ.left
            node.start, node.end = succ.start, succ.end
            node.right = succ.right
            self._pull_up(node)
            return node
        self._pull_up(node)
        return node

    def _collect_range(self, node, lo, hi, out):
        if node is None:
            return
        if node.max_end < lo:
            return
        self._collect_range(node.left, lo, hi, out)
        if node.start < hi and node.end >= lo:
            out.append((node.start, node.end))
        if node.start <= hi:
            self._collect_range(node.right, lo, hi, out)

    def _collect_point(self, node, x, out):
        if node is None:
            return
        if node.max_end < x:
            return
        self._collect_point(node.left, x, out)
        if node.start <= x <= node.end:
            out.append((node.start, node.end))
        if node.start <= x:
            self._collect_point(node.right, x, out)
