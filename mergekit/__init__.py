"""mergekit：一个纯标准库的序列比较与三方合并工具。

当前对外能力是 diff 与 merge 两道最朴素的功能：diff 逐位比较两段序列，
列出差在哪些下标；merge 在两侧都与基线一致时把改动抄过去，两侧都改过就
报冲突。基于编辑脚本的三方合并、可注入的冲突策略与输入规模上限都留待在这
个基础上补齐。
"""

from .diff import (
    ADD,
    EQUAL,
    REMOVE,
    REPLACE,
    Change,
    changes_only,
    diff,
    ensure_sequence,
    has_changes,
)
from .errors import (
    DiffError,
    InputLimitError,
    MergeConflictError,
    MergeKitError,
    StrategyError,
)
from .merge import changed_indices, merge, same_list

__all__ = [
    "ADD",
    "Change",
    "DiffError",
    "EQUAL",
    "InputLimitError",
    "MergeConflictError",
    "MergeKitError",
    "REMOVE",
    "REPLACE",
    "StrategyError",
    "changed_indices",
    "changes_only",
    "diff",
    "ensure_sequence",
    "has_changes",
    "merge",
    "same_list",
]