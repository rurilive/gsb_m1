"""把同一 trace 的 span 挂成调用树。

树由 Node 组成，每个 Node 包一条 span 和它的直接子 span。一个 trace 可以
有多个根（一条链路被拆到多个进程上报时会出现），Tree.roots 是这一层的入口；
父 span 始终没有出现、指向自身或互相指向成环的那些 span 挂在
Tree.unresolved 上：不丢，也不把环挂进树里。
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


def build_tree(trace_id, spans):
    """把一条 trace 的 span 挂成 Tree。

    兄弟之间、根之间都按 start_ms 升序、再按 span_id 字典序升序排，
    与到达顺序无关：同一批 span 不管按什么顺序喂进来，重建结果逐字节
    一致。parent_id 为空的 span 是根；parent_id 指向的 span 不存在、
    指向自身或互相指向成环的 span 归入 Tree.unresolved。
    """
    ordered = sorted(spans, key=lambda span: (span.start_ms, span.span_id))
    nodes = {}
    for span in ordered:
        nodes[span.span_id] = Node(span)

    # 按 parent_id 挂树；ordered 顺序即兄弟排序，children 天然有序。
    roots = []
    for span in ordered:
        node = nodes[span.span_id]
        if span.parent_id is None:
            roots.append(node)
        else:
            parent = nodes.get(span.parent_id)
            if parent is not None:
                parent.children.append(node)

    # 从根出发不可达的节点：父没出现、指向自身、或互相指向成环。沿
    # parent 链向上走永远到不了根，统一归入 unresolved；子节点拆开
    # 平铺，保证 unresolved 里也走不出环。
    reachable = set()
    stack = list(roots)
    while stack:
        node = stack.pop()
        if id(node) in reachable:
            continue
        reachable.add(id(node))
        stack.extend(node.children)

    unresolved = []
    for span in ordered:
        node = nodes[span.span_id]
        if id(node) not in reachable:
            node.children = []
            unresolved.append(node)

    return Tree(trace_id, roots, unresolved)


def build_trees(by_trace):
    """trace_id -> [Span] 的映射建成 Tree 列表，trace 按 trace_id 排序。"""
    return [build_tree(trace_id, by_trace[trace_id])
            for trace_id in sorted(by_trace)]
