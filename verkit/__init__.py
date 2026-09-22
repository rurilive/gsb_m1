"""verkit: 语义化版本（semver 2.0.0）的解析、比较与区间匹配。"""

from .range import best, match, normalize, overlaps, parse_range
from .version import Version, compare, parse_version

__all__ = [
    "Version",
    "compare",
    "parse_version",
    "parse_range",
    "match",
    "best",
    "overlaps",
    "normalize",
]
