"""调用树的文本渲染、缓存快照与汇总统计。"""


def _walk(node, depth=0):
    """先序深度遍历，逐个产出 (深度, Node)。根的深度是 0。"""
    yield depth, node
    for child in node.children:
        for item in _walk(child, depth + 1):
            yield item


def render_tree(tree):
    """渲染成缩进文本，一层两个空格，每行 "名字 (耗时ms)"。

    空树渲染成空串；行与行之间用一个换行隔开。
    """
    lines = []
    for root in tree.roots:
        for depth, node in _walk(root):
            lines.append("%s%s (%dms)" % ("  " * depth, node.span.name,
                                          node.span.duration_ms))
    return "\n".join(lines)


def snapshot(tree):
    """缓存用的规范串：第一行是 trace_id，之后每个 span 一行。

    行格式：缩进（一层两个空格）+ span_id + 服务名 + 耗时，服务名缺省时
    用 "-" 占位。
    """
    lines = ["trace %s" % tree.trace_id]
    for root in tree.roots:
        for depth, node in _walk(root):
            span = node.span
            lines.append("%s%s %s %dms" % ("  " * depth, span.span_id,
                                           span.service or "-",
                                           span.duration_ms))
    return "\n".join(lines)


def summary(tree):
    """汇总统计。

    返回 dict，键有 spans（树里的 span 数）、roots（根数）、
    unresolved（没有挂上树的 span 数）、total_ms（耗时合计）、
    max_depth（最大层深，根的深度是 0）。
    """
    spans = 0
    total_ms = 0
    max_depth = 0
    for root in tree.roots:
        for depth, node in _walk(root):
            spans += 1
            total_ms += node.span.duration_ms
            if depth > max_depth:
                max_depth = depth
    return {
        "spans": spans,
        "roots": len(tree.roots),
        "unresolved": len(tree.unresolved),
        "total_ms": total_ms,
        "max_depth": max_depth,
    }
