"""tracectx: 批处理里的跨线程执行小工具。"""

from tracectx.batch import ItemFailure, first_failure, map_batch
from tracectx.detached import async_call, run_detached
from tracectx.gate import Gate
from tracectx.trace import (
    Chain,
    Span,
    TracedThread,
    TracedThreadPoolExecutor,
    begin_chain,
    correlation_id,
    current_chain,
    current_span,
    format_report,
    get_slow_threshold,
    set_slow_threshold,
    span,
)

__all__ = [
    "Chain",
    "Gate",
    "ItemFailure",
    "Span",
    "TracedThread",
    "TracedThreadPoolExecutor",
    "async_call",
    "begin_chain",
    "correlation_id",
    "current_chain",
    "current_span",
    "first_failure",
    "format_report",
    "get_slow_threshold",
    "map_batch",
    "run_detached",
    "set_slow_threshold",
    "span",
]
