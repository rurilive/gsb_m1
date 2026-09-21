"""关键路径：根到叶耗时之和最大的那条链。

耗时已经按非负钳过（时钟回拨的 span 按 0 计）。并列时取 span_id
序列字典序最小的那条：两条链第一个不同的位置就是各自子节点的
span_id，所以同层并列只要取 span_id 最小的子节点即可。
"""


def _chain_totals(roots):
    """后序遍历，算出每个节点打头的最大链耗时，返回 id(node) -> 耗时。"""
    totals = {}
    for root in roots:
        stack = [(root, False)]
        while stack:
            node, expanded = stack.pop()
            if expanded:
                total = node.span.duration_ms
                if node.children:
                    total += max(totals[id(child)]
                                 for child in node.children)
                totals[id(node)] = total
            else:
                stack.append((node, True))
                for child in node.children:
                    stack.append((child, False))
    return totals


def critical_path(tree):
    """整棵树的关键路径，返回从根到叶的 span_id 列表。

    并列时取 span_id 序列字典序最小的那条；空树返回空列表。
    """
    if not tree.roots:
        return []
    totals = _chain_totals(tree.roots)
    best_total = max(totals[id(root)] for root in tree.roots)
    node = min((root for root in tree.roots
                if totals[id(root)] == best_total),
               key=lambda root: root.span.span_id)
    path = []
    while True:
        path.append(node.span.span_id)
        if not node.children:
            return path
        best_child = max(totals[id(child)] for child in node.children)
        node = min((child for child in node.children
                    if totals[id(child)] == best_child),
                   key=lambda child: child.span.span_id)
