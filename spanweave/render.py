"""调用树的文本渲染、缓存快照与汇总统计。"""


def _walk_roots(roots):
    """按根顺序先序遍历一整片林子，产出 (深度, Node)。"""
    stack = [(0, root) for root in reversed(roots)]
    while stack:
        depth, node = stack.pop()
        yield depth, node
        for child in reversed(node.children):
            stack.append((depth + 1, child))


def render_tree(tree):
    """渲染成缩进文本，一层两个空格，每行 "名字 (耗时ms)"。

    空树渲染成空串；行与行之间用一个换行隔开。
    """
    lines = []
    for depth, node in _walk_roots(tree.roots):
        lines.append("%s%s (%dms)" % ("  " * depth, node.span.name,
                                      node.span.duration_ms))
    return "\n".join(lines)


def snapshot(tree):
    """缓存用的规范串：第一行是 trace_id，之后每个 span 一行。

    行格式：缩进（一层两个空格）+ span_id + 服务名 + 耗时，服务名缺省时
    用 "-" 占位。
    """
    lines = ["trace %s" % tree.trace_id]
    for depth, node in _walk_roots(tree.roots):
        span = node.span
        lines.append("%s%s %s %dms" % ("  " * depth, span.span_id,
                                       span.service or "-",
                                       span.duration_ms))
    return "\n".join(lines)


def summary(tree):
    """汇总统计。

    返回 dict，键有 spans（树里的 span 数）、roots（根数）、
    unresolved（没有挂上树的 span 数）、total_ms（耗时合计）、
    clock_skew（end_ms 早于 start_ms 的 span 数，含未挂树的）、
    max_depth（最大层深，根的深度是 0）。
    """
    spans = 0
    total_ms = 0
    max_depth = 0
    clock_skew = 0
    for depth, node in _walk_roots(tree.roots):
        spans += 1
        total_ms += node.span.duration_ms
        if depth > max_depth:
            max_depth = depth
        if node.span.clock_skew:
            clock_skew += 1
    for node in tree.unresolved:
        if node.span.clock_skew:
            clock_skew += 1
    return {
        "spans": spans,
        "roots": len(tree.roots),
        "unresolved": len(tree.unresolved),
        "total_ms": total_ms,
        "clock_skew": clock_skew,
        "max_depth": max_depth,
    }
