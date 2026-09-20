"""changelogd: 按版本号记录字段变更的日志，支持多分支合并。"""

from changelogd.changelog import Change, ChangeLog
from changelogd.merge import (
    DELETE,
    Branch,
    Candidate,
    Conflict,
    MergeResult,
    MergedChange,
    fork,
    last_write_wins,
    merge,
    prefer_branch,
)

__all__ = [
    "Change",
    "ChangeLog",
    "DELETE",
    "Branch",
    "Candidate",
    "Conflict",
    "MergeResult",
    "MergedChange",
    "fork",
    "last_write_wins",
    "merge",
    "prefer_branch",
]
