"""regexlib: 一个从字面匹配起步的规则匹配小库。"""

from regexlib.pattern import (
    LiteralPat,
    RegexError,
    literal_match,
    literal_search,
)

__all__ = ["LiteralPat", "RegexError", "literal_match", "literal_search"]
