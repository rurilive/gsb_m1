"""rankly: a tiny ranking toolkit (baseline).

Only the naive sort-based Top-K helper is exported today.
"""

from .topk import SortTopK

__all__ = ["SortTopK"]
