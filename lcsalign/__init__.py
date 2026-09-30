"""lcsalign: 最长公共子序列与序列比对。"""

from lcsalign.sequence import (
    EmptySequenceError,
    SequenceError,
    lcs_length,
    lcs_sequence,
    summary,
)

__all__ = [
    "EmptySequenceError",
    "SequenceError",
    "lcs_length",
    "lcs_sequence",
    "summary",
]
