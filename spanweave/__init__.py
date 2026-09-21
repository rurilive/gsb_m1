"""spanweave：把本地采集的 span 重建成调用树的库。

按 trace 分组挂树，输出缩进文本、缓存用的规范快照、统计摘要与关键路径。
只依赖 Python 标准库。
"""

from .builder import Node, Tree, build_tree, build_trees
from .critical import critical_path
from .model import Span, SpanError
from .render import render_tree, snapshot, summary
from .store import SpanStore

__version__ = "0.3.0"

__all__ = [
    "Node",
    "Span",
    "SpanError",
    "SpanStore",
    "Tree",
    "build",
    "build_tree",
    "build_trees",
    "critical_path",
    "render_tree",
    "snapshot",
    "summary",
]


def build(records):
    """一次把一批记录吃进来并重建，返回按 trace_id 排序的 Tree 列表。"""
    store = SpanStore()
    store.feed(records)
    return store.traces()
