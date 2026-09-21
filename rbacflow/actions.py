"""动作名的规范与拆解。

动作名是冒号分隔的小写段，比如 "docs:read"、"pkg:sub:list"。
每一段以字母开头，后面可以跟字母和数字，段不能为空。

授予和拒绝可以写尾部通配："pkg:*" 盖住 "pkg:" 名下的整片子动作，
"*" 盖住一切。星号只能落在最后一段，"*:read"、"pkg:*:list" 都不合法。
"""

import re

from .errors import InvalidAction

_SEGMENT = r"[a-z][a-z0-9]*"
_PLAIN = re.compile(_SEGMENT + r"(?::" + _SEGMENT + r")*")
_WILD = re.compile(
    r"\*|"
    + _SEGMENT + r"(?::" + _SEGMENT + r")*"      # 精确动作 docs:read
    + r"|"
    + _SEGMENT + r"(?::" + _SEGMENT + r")*:\*"   # 尾部通配 pkg:*
)


def validate(action):
    """校验具体动作名（不接受通配），通过就原样返回，不合法抛 InvalidAction。"""
    if not isinstance(action, str) or _PLAIN.fullmatch(action) is None:
        raise InvalidAction("非法动作名: %r" % (action,))
    return action


def validate_pattern(pattern):
    """校验授予/拒绝用的动作模式（可以是尾部通配），通过就原样返回。"""
    if not isinstance(pattern, str) or _WILD.fullmatch(pattern) is None:
        raise InvalidAction("非法动作模式: %r" % (pattern,))
    return pattern


def segments(action):
    """把动作名拆成段，"pkg:sub:list" 拆成 ["pkg", "sub", "list"]。"""
    return validate(action).split(":")


def is_wildcard(pattern):
    """模式是不是尾部通配："pkg:*"、"*" 为真，"pkg:read" 为假。"""
    validate_pattern(pattern)
    return pattern == "*" or pattern.endswith(":*")


def pattern_parts(pattern):
    """把模式拆成（固定段元组, 是否通配）。

    "pkg:sub:*" 拆成 (("pkg", "sub"), True)，"docs:read" 拆成
    (("docs", "read"), False)，"*" 拆成 ((), True)。
    """
    validate_pattern(pattern)
    if pattern == "*":
        return (), True
    if pattern.endswith(":*"):
        return tuple(pattern[:-2].split(":")), True
    return tuple(pattern.split(":")), False


def matches(pattern, action):
    """模式能不能盖住这个具体动作。

    精确模式只认同名；"pkg:*" 匹配 "pkg:read"、"pkg:sub:list"，
    但不匹配 "pkg" 本身；"*" 匹配一切合法动作。
    """
    fixed, wild = pattern_parts(pattern)
    actual = tuple(validate(action).split(":"))
    if not wild:
        return fixed == actual
    if not fixed:
        return True
    return actual[:len(fixed)] == fixed and len(actual) > len(fixed)


def candidates(action):
    """一个动作可能被哪些形状的模式命中，按具体程度从高到低。

    "pkg:sub:list" 给出 ["pkg:sub:list", "pkg:sub:*", "pkg:*", "*"]：
    精确在前，然后是由长到短的前缀通配。
    """
    parts = validate(action).split(":")
    out = [":".join(parts)]
    for cut in range(len(parts) - 1, 0, -1):
        out.append(":".join(parts[:cut]) + ":*")
    out.append("*")
    return out
