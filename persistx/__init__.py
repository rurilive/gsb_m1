"""persistx: a small pure-stdlib sequence library.

The public surface currently exports only the baseline mutable list.
"""

from .seq import MutList

__all__ = ["MutList"]
