"""把同一 trace 的 span 挂成调用树。

树由 Node 组成，每个 Node 包一条 span 和它的直接子 span。一个 trace 可以
有多个根（一条链路被拆到多个进程上报时会出现），Tree.roots 是这一层的入口；
父 span 始终没有出现的那些 span 挂在 Tree.unresolved 上。
"""


class Node:
    """树上的一段：一条 span 加上它的直接子 span。"""

    __slots__ = ("span", "children")

    def __init__(self, span):
        self.span = span
        self.children = []

    def __repr__(self):
        return "Node(%s)" % self.span.span_id


class Tree:
    """一条 trace 重建出来的调用树。"""

    def __init__(self, trace_id, roots, unresolved):
        self.trace_id = trace_id
        self.roots = roots
        self.unresolved = unresolved


def _nearest_previous(nodes, node):
    """同 trace 里开始时间不晚于 node 的最近一条，排除自身。"""
    best = None
    for other in nodes:
        if other is node or other.span.trace_id != node.span.trace_id:
            continue
        if other.span.start_ms > node.span.start_ms:
            continue
        if best is None or other.span.start_ms > best.span.start_ms:
            best = other
    return best


def build_tree(trace_id, spans):
    """把一条 trace 的 span 挂成 Tree。"""
    nodes = [Node(span) for span in spans]

    def node_of(span_id):
        for node in nodes:
            if node.span.span_id == span_id:
                return node
        return None

    roots = []
    for node in nodes:
        span = node.span
        parent = None
        if span.parent_id is not None:
            parent = node_of(span.parent_id)
        if parent is None:
            # 父不在数据里，或者压根没有 parent_id（跨进程上报常丢这个字段）：
            # 按开始时间就近挂到同 trace 里前一条 span 上，别让子树浮在根上
            parent = _nearest_previous(nodes, node)
        if parent is None:
            roots.append(node)
        else:
            parent.children.append(node)

    for node in nodes:
        node.children.sort(key=lambda child: child.span.start_ms)

    return Tree(trace_id, roots, [])


def build_trees(by_trace):
    """trace_id -> [Span] 的映射建成 Tree 列表，trace 按 trace_id 排序。"""
    return [build_tree(trace_id, by_trace[trace_id])
            for trace_id in sorted(by_trace)]
