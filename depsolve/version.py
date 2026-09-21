"""版本号与区间约束。"""

import re

_REQ_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_-]*)\s*(.*)$")
_OPS = (">=", "<=", "==", "!=", ">", "<")


def parse_version(text):
    """'2.1.0' -> (2, 1, 0)，按数值逐段比较。"""
    return tuple(int(part) for part in text.strip().split("."))


def parse_requirement(text):
    """'json>=2.0,<2.2' -> ('json', [('>=', (2, 0)), ('<', (2, 2))]')。

    不带约束时第二个元素为空列表，表示任意版本。
    """
    m = _REQ_RE.match(text)
    if not m:
        raise ValueError(f"无法解析依赖声明: {text!r}")
    name, rest = m.group(1), m.group(2).strip()
    constraints = []
    if rest:
        for part in rest.split(","):
            part = part.strip()
            for op in _OPS:
                if part.startswith(op):
                    constraints.append((op, parse_version(part[len(op):])))
                    break
            else:
                raise ValueError(f"无法解析版本约束: {part!r}")
    return name, constraints


def satisfies(version, constraints):
    """version 字符串是否满足全部约束。"""
    v = parse_version(version)
    for op, target in constraints:
        ok = {
            ">=": v >= target,
            "<=": v <= target,
            "==": v == target,
            "!=": v != target,
            ">": v > target,
            "<": v < target,
        }[op]
        if not ok:
            return False
    return True
