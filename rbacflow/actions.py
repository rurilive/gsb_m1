"""动作名的规范与拆解。

动作名是冒号分隔的小写段，比如 "docs:read"、"pkg:sub:list"。
每一段以字母开头，后面可以跟字母和数字，段不能为空。
"""

import re

from .errors import InvalidAction

_SEGMENT = r"[a-z][a-z0-9]*"
_PLAIN = re.compile(_SEGMENT + r"(?::" + _SEGMENT + r")*")


def validate(action):
    """校验动作名，通过就原样返回，不合法抛 InvalidAction。"""
    if not isinstance(action, str) or _PLAIN.fullmatch(action) is None:
        raise InvalidAction("非法动作名: %r" % (action,))
    return action


def segments(action):
    """把动作名拆成段，"pkg:sub:list" 拆成 ["pkg", "sub", "list"]。"""
    return validate(action).split(":")
