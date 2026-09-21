"""cdcparse: 本地 binlog 风格 JSON 行事件流的读取与投递。

逐条读取事件，并有一个把变更立刻推给下游的简单通道。
"""

from cdcparse.events import (
    Event,
    ParseError,
    begin_line,
    commit_line,
    data_line,
    ddl_line,
    parse_line,
    txn_lines,
)
from cdcparse.relay import StreamRelay
from cdcparse.sink import MemorySink
from cdcparse.stream import EventReader, FileSource, MemorySource

__all__ = [
    "Event",
    "EventReader",
    "FileSource",
    "MemorySink",
    "MemorySource",
    "ParseError",
    "StreamRelay",
    "begin_line",
    "commit_line",
    "data_line",
    "ddl_line",
    "parse_line",
    "txn_lines",
]
