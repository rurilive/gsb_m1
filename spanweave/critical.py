"""关键路径：根到叶耗时之和最大的那条链。"""


def _best_below(roots):
    """在若干棵子树里选根到叶耗时之和最大的链。

    迭代后序计算，几千层的深链也不会撑爆栈。返回
    ``(总耗时, [span_id, ...])``；耗时并列时取 span_id 序列字典序
    最小的那条。
    """
    totals = {}
    paths = {}
    stack = [(root, False) for root in roots]
    while stack:
        node, processed = stack.pop()
        if processed:
            duration = node.span.duration_ms
            # 只有叶节点能以自身收尾；有子节点时必须延伸到某个叶子。
            best_total = None
            best_ids = None
            for child in node.children:
                total = duration + totals[id(child)]
                ids = [node.span.span_id] + paths[id(child)]
                if best_total is None or total > best_total or (
                        total == best_total and ids < best_ids):
                    best_total = total
                    best_ids = ids
            if best_total is None:
                best_total = duration
                best_ids = [node.span.span_id]
            totals[id(node)] = best_total
            paths[id(node)] = best_ids
        elif id(node) not in totals:
            stack.append((node, True))
            for child in reversed(node.children):
                stack.append((child, False))

    best_total = None
    best_ids = None
    for root in roots:
        total = totals[id(root)]
        ids = paths[id(root)]
        if best_total is None or total > best_total or (
                total == best_total and ids < best_ids):
            best_total = total
            best_ids = ids
    return best_total, best_ids


def critical_path(tree):
    """整棵树的关键路径，返回从根到叶的 span_id 列表。

    并列时取 span_id 序列字典序最小的那条；空树返回空列表。
    """
    if not tree.roots:
        return []
    _, best_ids = _best_below(tree.roots)
    return best_ids
