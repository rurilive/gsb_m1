"""logpipe: a small local pipeline for nested structured log records.

Records are plain dictionaries that may nest dictionaries and lists. The
pipeline serializes each record to one JSON line and hands the line to a
sink. Paths address values inside a record, see :mod:`logpipe.paths`.
"""

from .paths import (
    PathError,
    format_path,
    get_path,
    parse_path,
    set_path,
    walk_leaves,
)
from .pipeline import LogPipeline
from .redact import (
    Redactor,
    RuleError,
    apply_mask,
    format_pattern,
    mask_all,
    mask_card,
    mask_phone,
    parse_pattern,
)
from .records import check_record, clone, dumps, is_leaf, loads
from .sink import JsonlFileSink, MemorySink

__all__ = [
    "JsonlFileSink",
    "LogPipeline",
    "MemorySink",
    "PathError",
    "Redactor",
    "RuleError",
    "apply_mask",
    "check_record",
    "clone",
    "dumps",
    "format_pattern",
    "format_path",
    "get_path",
    "is_leaf",
    "loads",
    "mask_all",
    "mask_card",
    "mask_phone",
    "parse_pattern",
    "parse_path",
    "set_path",
    "walk_leaves",
]
