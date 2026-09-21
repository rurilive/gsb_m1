"""采集缓冲：按到达顺序吃进记录，按 trace 分组交给 builder。

采集端是并发上报的，记录可以分多批 feed 进来，同一个 span_id 可能因为
重试被上报多次。
"""

from .builder import build_trees
from .model import Span


class SpanStore:
    """到达顺序不定、可能重传的 span 缓冲。

    父 span 已经在缓冲里的记录直接入册；父还没到的先搁一边。
    """

    def __init__(self):
        self._by_id = {}     # span_id -> Span，判重
        self._by_trace = {}  # trace_id -> [Span]，按到达顺序

    def feed(self, records):
        """按到达顺序吃进一批记录，重复的 span_id 只留先到的一条。"""
        for record in records:
            span = Span.from_record(record)
            if span.span_id in self._by_id:
                continue
            if span.parent_id is not None and span.parent_id not in self._by_id:
                # 父 span 还没到：这条先不要了
                continue
            self._by_id[span.span_id] = span
            self._by_trace.setdefault(span.trace_id, []).append(span)

    def traces(self):
        """把缓冲里的 span 重建为调用树，trace 按 trace_id 排序。"""
        return build_trees(self._by_trace)
