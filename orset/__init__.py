"""orset: 支持 add、remove 与 contains 的基础集合。"""

from .set import ORSet, SetError

__all__ = ["ORSet", "SetError"]