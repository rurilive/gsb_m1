"""span 记录：采集端上报的一条调用链片段。

一条记录对应一次调用，字段有 trace_id、span_id、parent_id、name、
service、start_ms、end_ms，时间是整数毫秒。
"""


class SpanError(ValueError):
    """记录字段不合法。"""


class Span:
    """一条 span。parent_id 为 None 表示它没有父。"""

    __slots__ = ("trace_id", "span_id", "parent_id", "name", "service",
                 "start_ms", "end_ms")

    def __init__(self, trace_id, span_id, parent_id, name, service,
                 start_ms, end_ms):
        self.trace_id = trace_id
        self.span_id = span_id
        self.parent_id = parent_id
        self.name = name
        self.service = service
        self.start_ms = start_ms
        self.end_ms = end_ms

    @classmethod
    def from_record(cls, record):
        """从采集端的一条 dict 记录构造 Span。

        parent_id 允许缺省或为空串，两者都表示这条 span 没有父。
        """
        if not isinstance(record, dict):
            raise SpanError("记录必须是 dict: %r" % (record,))
        try:
            trace_id = record["trace_id"]
            span_id = record["span_id"]
            start_ms = record["start_ms"]
            end_ms = record["end_ms"]
        except KeyError as exc:
            raise SpanError("记录缺少字段 %s" % exc.args[0])
        if not trace_id or not span_id:
            raise SpanError("trace_id 与 span_id 不能为空")
        if not isinstance(start_ms, int) or not isinstance(end_ms, int):
            raise SpanError("时间戳必须是整数毫秒")
        return cls(
            trace_id,
            span_id,
            record.get("parent_id") or None,
            record.get("name") or span_id,
            record.get("service") or "",
            start_ms,
            end_ms,
        )

    @property
    def duration_ms(self):
        """这次调用的耗时，毫秒。"""
        return self.end_ms - self.start_ms

    def __repr__(self):
        return "Span(%s/%s)" % (self.trace_id, self.span_id)
