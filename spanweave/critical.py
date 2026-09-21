"""关键路径：根到叶耗时之和最大的那条链。"""


def _best(node):
    """以 node 打头的最大耗时链，返回 (总耗时, [span_id, ...])。"""
    best_total = node.span.duration_ms
    best_ids = [node.span.span_id]
    for child in node.children:
        child_total, child_ids = _best(child)
        total = node.span.duration_ms + child_total
        if total > best_total:
            best_total = total
            best_ids = [node.span.span_id] + child_ids
    return best_total, best_ids


def critical_path(tree):
    """整棵树的关键路径，返回从根到叶的 span_id 列表。

    并列时取 span_id 序列字典序最小的那条；空树返回空列表。
    """
    best_total = None
    best_ids = None
    for root in tree.roots:
        total, ids = _best(root)
        if best_total is None or total > best_total:
            best_total = total
            best_ids = ids
    return best_ids if best_ids is not None else []
