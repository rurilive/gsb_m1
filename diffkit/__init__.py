"""diffkit: unified diff 生成与补丁应用/回滚。"""

from .diff import unified_diff
from .patch import apply_patch, parse_patch, unapply_patch

__all__ = ["unified_diff", "parse_patch", "apply_patch", "unapply_patch"]
