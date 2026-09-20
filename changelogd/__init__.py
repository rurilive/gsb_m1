"""changelogd: 按版本号记录字段变更的日志。"""

from changelogd.merge import (
    Candidate,
    Conflict,
    DELETE,
    MergeResult,
    MergedChange,
    first_wins,
    latest_ts_wins,
    merge,
)

__all__ = [
    "Candidate",
    "Conflict",
    "DELETE",
    "MergeResult",
    "MergedChange",
    "first_wins",
    "latest_ts_wins",
    "merge",
]
