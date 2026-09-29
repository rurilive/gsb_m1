"""ropetex: a small plain-text buffer library.

The public surface currently exports only the baseline flat text buffer.
"""

from .text import FlatText

__all__ = ["FlatText"]
