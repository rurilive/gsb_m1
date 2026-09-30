"""suffixarr：纯标准库的后缀数组与最长公共前缀朴素工具（改造前基线）。"""

from .suffix import NaiveSuffix, SuffixError, SuffixIndexError

__all__ = ["NaiveSuffix", "SuffixError", "SuffixIndexError"]
