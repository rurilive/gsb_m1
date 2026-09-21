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


def build_tree(trace_id, spans):
    """把一条 trace 的 span 挂成 Tree。

    只按 ``parent_id`` 挂接：父缺失（始终没到、跨 trace 指向）或参与
    成环的 span 不会硬挂到别的链路上，连同环上其它 span 一并放进
    ``Tree.unresolved``，一条都不丢。兄弟与根都按
    ``(start_ms, span_id)`` 排序，因此结果与到达顺序无关。
    """
    nodes = {span.span_id: Node(span) for span in spans}

    roots = []
    for span_id, node in nodes.items():
        parent_id = node.span.parent_id
        if parent_id is None:
            roots.append(node)
        else:
            parent = nodes.get(parent_id)
            if parent is not None:
                parent.children.append(node)

    # 从所有根出发做可达性遍历：能走到的才是树上的节点。指向缺失父的
    # span、互指成环的 span 都不可达，既不会进树也不会被丢。
    reachable = set()
    stack = list(roots)
    while stack:
        node = stack.pop()
        if id(node) in reachable:
            continue
        reachable.add(id(node))
        stack.extend(node.children)

    order_key = lambda node: (node.span.start_ms, node.span.span_id)
    for node in nodes.values():
        node.children.sort(key=order_key)
    roots.sort(key=order_key)

    unresolved = [node for node in nodes.values()
                  if id(node) not in reachable]
    unresolved.sort(key=order_key)
    # unresolved 之间不允许保留父子挂接（可能成环），渲染与统计只看 roots。
    for node in unresolved:
        node.children = []

    return Tree(trace_id, roots, unresolved)


def build_trees(by_trace):
    """trace_id -> [Span] 的映射建成 Tree 列表，trace 按 trace_id 排序。"""
    return [build_tree(trace_id, by_trace[trace_id])
            for trace_id in sorted(by_trace)]
