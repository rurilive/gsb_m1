"""pipeflow：一个极简的流式数据处理包。

核心是逐条处理的 run_stream，以及搭在它之上的可组合、有背压的批处理管道：
Source、Map、Filter、FlatMap、Batch、Sink 六个算子由 Pipeline 串成一条链。
"""

from .core import run_stream
from .pipeline import Pipeline, QueueFull
from .stages import (
    Batch,
    CollectSink,
    Filter,
    FlatMap,
    IterSource,
    Map,
    Sink,
    Source,
    Stage,
    StageStats,
)

__all__ = [
    "run_stream",
    "Pipeline",
    "QueueFull",
    "Source",
    "IterSource",
    "Stage",
    "Map",
    "Filter",
    "FlatMap",
    "Batch",
    "Sink",
    "CollectSink",
    "StageStats",
]