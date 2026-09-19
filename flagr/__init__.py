"""flagr: 特性开关规则引擎。

文本 DSL -> 编译期校验 -> matcher 树 -> 求值决策 + 解释，纯标准库。
"""

from .compiler import COMBINATOR_TABLE, OP_TABLE, compile_rules
from .engine import Decision, FlagEngine, FlagSpec, Rule
from .errors import FlagrError, RuleCompileError, UnknownFlagError
from .lexer import Token, tokenize
from .matchers import (
    All, Any, Compare, Contains, Equals, InSet, Matcher, NotEquals,
)

__all__ = [
    "COMBINATOR_TABLE", "OP_TABLE", "compile_rules",
    "Decision", "FlagEngine", "FlagSpec", "Rule",
    "FlagrError", "RuleCompileError", "UnknownFlagError",
    "Token", "tokenize",
    "All", "Any", "Compare", "Contains", "Equals", "InSet", "Matcher",
    "NotEquals",
]
