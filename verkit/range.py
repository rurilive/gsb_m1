"""semver 区间：解析、匹配、择优、重叠判断与规范化。

语法（npm 常用子集）：
- 空格分隔的多个比较子是 AND；``||`` 分隔的多个分支是 OR
- 比较子：``>=`` ``>`` ``<=`` ``<`` ``=`` ``!=`` 前缀或裸版本（等价于 ``=``）
- 缺省段补 ``.0``：``>=1.2`` 即 ``>=1.2.0``
- 通配：``x`` / ``X`` / ``*`` 可出现在 minor/patch 位或整体（``1.x``、``1.2.x``、``*``）
- ``^`` / ``~`` 按 npm 语义展开（含 0.x 特例）
- prerelease 默认不匹配；同一 OR 分支里若有比较子对同一 x.y.z
  显式携带 prerelease，则该 x.y.z 的 prerelease 也参与匹配
"""

import re

from .version import Version, parse_version

_WILDCARDS = ("x", "X", "*")
_TOKEN_RE = re.compile(r"^(\^|~|<=|>=|!=|<|>|=)?(\S+)$")


class Comparator:
    """单个比较子：运算符 + 完整版本。"""

    __slots__ = ("op", "version")

    def __init__(self, op, version):
        self.op = op
        self.version = version

    def matches(self, v):
        if self.op == "=":
            return v == self.version
        if self.op == "!=":
            return v != self.version
        if self.op == ">":
            return v > self.version
        if self.op == ">=":
            return v >= self.version
        if self.op == "<":
            return v < self.version
        if self.op == "<=":
            return v <= self.version
        raise ValueError(f"未知运算符: {self.op!r}")

    def __str__(self):
        if self.op == "=":
            return str(self.version)
        return f"{self.op}{self.version}"

    def __repr__(self):
        return f"Comparator({self.op!r}, {self.version!r})"


class _Branch:
    """一个 AND 分支：所有比较子同时满足。"""

    def __init__(self, comparators):
        self.comparators = list(comparators)

    def matches(self, v):
        if not all(c.matches(v) for c in self.comparators):
            return False
        if v.prerelease is None:
            return True
        tuple3 = (v.major, v.minor, v.patch)
        return any(
            c.version.prerelease is not None
            and (c.version.major, c.version.minor, c.version.patch) == tuple3
            for c in self.comparators
        )

    def __str__(self):
        return " ".join(str(c) for c in self.comparators) or "*"


class Range:
    """一个区间：若干 AND 分支的 OR。"""

    def __init__(self, branches):
        self.branches = list(branches)

    def matches(self, version):
        v = version if isinstance(version, Version) else parse_version(version)
        return any(b.matches(v) for b in self.branches)

    def __str__(self):
        return " || ".join(str(b) for b in self.branches)


def _split_partial(body):
    """把 ``1.2.3-alpha+build`` 拆成 (段列表, prerelease, build)。

    段为 int 或 None（通配符）；通配符只能出现在尾部。
    """
    core, _, build = body.partition("+")
    core, _, pre = core.partition("-")
    if not core:
        raise ValueError(f"缺少版本号: {body!r}")
    parts = []
    for seg in core.split("."):
        if seg in _WILDCARDS:
            parts.append(None)
        elif seg.isascii() and seg.isdigit() and (seg == "0" or not seg.startswith("0")):
            parts.append(int(seg))
        else:
            raise ValueError(f"非法版本段: {seg!r}")
    if len(parts) > 3:
        raise ValueError(f"版本段过多: {body!r}")
    for i, p in enumerate(parts):
        if p is not None and any(q is None for q in parts[:i]):
            raise ValueError(f"通配符后不能再跟具体段: {body!r}")
    if (pre or build) and (len(parts) != 3 or any(p is None for p in parts)):
        raise ValueError(f"带 prerelease/build 的比较子必须写全 x.y.z: {body!r}")
    return parts, pre or None, build or None


def _make_version(parts, pre, build):
    """缺省段补 0，并复用 parse_version 做严格校验。"""
    filled = [p if p is not None else 0 for p in parts] + [0] * (3 - len(parts))
    text = ".".join(str(n) for n in filled[:3])
    if pre:
        text += "-" + pre
    if build:
        text += "+" + build
    return parse_version(text)


def _caret_hi(parts):
    """^ 的上界：左起第一个非零段进位；0.x 特例按 npm 语义。"""
    major = parts[0] if len(parts) > 0 else None
    minor = parts[1] if len(parts) > 1 else None
    patch = parts[2] if len(parts) > 2 else None
    if major is None:
        return None  # ^x：任意版本
    if major > 0:
        return (major + 1, 0, 0)
    if minor is None:
        return (1, 0, 0)  # ^0
    if minor > 0:
        return (0, minor + 1, 0)
    if patch is None:
        return (0, 1, 0)  # ^0.0
    return (0, 0, patch + 1)  # ^0.0.x


def _tilde_hi(parts):
    """~ 的上界：只放开最后指定的一段。"""
    major = parts[0] if len(parts) > 0 else None
    minor = parts[1] if len(parts) > 1 else None
    if major is None:
        return None  # ~x：任意版本
    if minor is None:
        return (major + 1, 0, 0)
    return (major, minor + 1, 0)


def _expand_token(token):
    """一个 token 展开为一组 AND 比较子。"""
    m = _TOKEN_RE.match(token)
    if not m:
        raise ValueError(f"非法比较子: {token!r}")
    op = m.group(1) or "="
    parts, pre, build = _split_partial(m.group(2))
    if op in ("^", "~"):
        out = [Comparator(">=", _make_version(parts, pre, build))]
        hi = _caret_hi(parts) if op == "^" else _tilde_hi(parts)
        if hi is not None:
            out.append(Comparator("<", Version(*hi)))
        return out
    if any(p is None for p in parts):
        if op != "=":
            raise ValueError(f"通配符只能用于裸版本: {token!r}")
        if parts[0] is None:
            return []  # *：任意版本
        lo = _make_version(parts, None, None)
        if parts[1] is None:
            hi = Version(parts[0] + 1, 0, 0)
        else:
            hi = Version(parts[0], parts[1] + 1, 0)
        return [Comparator(">=", lo), Comparator("<", hi)]
    return [Comparator(op, _make_version(parts, pre, build))]


def parse_range(text):
    """解析区间文本为 Range；非法输入抛 ValueError。传 Range 则原样返回。"""
    if isinstance(text, Range):
        return text
    if not isinstance(text, str):
        raise ValueError(f"区间必须是字符串: {text!r}")
    branches = []
    for chunk in text.split("||"):
        comparators = []
        for token in chunk.split():
            comparators.extend(_expand_token(token))
        branches.append(_Branch(comparators))
    return Range(branches)


def match(version, rng):
    """判断 version（Version 或字符串）是否落在区间 rng（Range 或字符串）内。"""
    return parse_range(rng).matches(version)


def best(versions, rng):
    """满足区间的版本中优先级最高的一个；没有则返回 None。"""
    r = parse_range(rng)
    winner = None
    for item in versions:
        v = item if isinstance(item, Version) else parse_version(item)
        if r.matches(v) and (winner is None or v > winner):
            winner = v
    return winner


def _simple_interval(branch):
    """纯区间分支折成 (lo, lo_inc, hi, hi_inc)；含 != 或 prerelease 则返回 None。"""
    lo = hi = None
    lo_inc = hi_inc = False
    for c in branch.comparators:
        v = c.version
        if c.op == "!=" or v.prerelease is not None:
            return None
        if c.op in (">", ">=", "="):
            inc = c.op != ">"
            if lo is None or v > lo:
                lo, lo_inc = v, inc
            elif v == lo:
                lo_inc = lo_inc and inc
        if c.op in ("<", "<=", "="):
            inc = c.op != "<"
            if hi is None or v < hi:
                hi, hi_inc = v, inc
            elif v == hi:
                hi_inc = hi_inc and inc
    return (lo, lo_inc, hi, hi_inc)


def _interval_empty(iv):
    lo, lo_inc, hi, hi_inc = iv
    if lo is None or hi is None:
        return False
    return lo > hi or (lo == hi and not (lo_inc and hi_inc))


def _touching(a, b):
    """两区间重叠或端点相接（至少一端闭合）。"""
    if a[2] is None or b[0] is None:
        return True
    if a[2] > b[0]:
        return True
    return a[2] == b[0] and (a[3] or b[1])


def _union(a, b):
    lo, lo_inc = a[0], a[1]
    if a[0] is None:
        lo, lo_inc = b[0], b[1]
    elif b[0] is not None:
        if b[0] < a[0]:
            lo, lo_inc = b[0], b[1]
        elif b[0] == a[0]:
            lo_inc = a[1] or b[1]
    if a[2] is None or b[2] is None:
        hi, hi_inc = None, False
    elif b[2] > a[2]:
        hi, hi_inc = b[2], b[3]
    elif b[2] == a[2]:
        hi, hi_inc = a[2], a[3] or b[3]
    else:
        hi, hi_inc = a[2], a[3]
    return (lo, lo_inc, hi, hi_inc)


def _merge_intervals(intervals):
    intervals = [iv for iv in intervals if not _interval_empty(iv)]
    intervals.sort(key=lambda iv: (iv[0] is not None, iv[0]))
    merged = []
    for iv in intervals:
        if merged and _touching(merged[-1], iv):
            merged[-1] = _union(merged[-1], iv)
        else:
            merged.append(iv)
    return merged


def _render_interval(iv):
    lo, lo_inc, hi, hi_inc = iv
    if lo is None and hi is None:
        return "*"
    if lo is not None and hi is not None and lo == hi and lo_inc and hi_inc:
        return str(lo)
    parts = []
    if lo is not None:
        parts.append((">=" if lo_inc else ">") + str(lo))
    if hi is not None:
        parts.append(("<=" if hi_inc else "<") + str(hi))
    return " ".join(parts)


def normalize(rng):
    """把重叠或相邻的 OR 分支合并成最简式字符串；match 结果集不变。

    只合并不含 ``!=`` 与 prerelease 的纯区间分支，其余分支原样保留。
    不可满足的区间规范化为 ``<0.0.0``（空集）。
    """
    r = parse_range(rng)
    intervals = []
    others = []
    for branch in r.branches:
        iv = _simple_interval(branch)
        if iv is None:
            others.append(str(branch))
        else:
            intervals.append(iv)
    parts = [_render_interval(iv) for iv in _merge_intervals(intervals)]
    parts.extend(others)
    return " || ".join(parts) if parts else "<0.0.0"


def _branches_overlap(ba, bb):
    lo = hi = None
    lo_inc = hi_inc = False
    comparators = list(ba.comparators) + list(bb.comparators)
    for c in comparators:
        v = c.version
        if c.op in (">", ">=", "="):
            inc = c.op != ">"
            if lo is None or v > lo:
                lo, lo_inc = v, inc
            elif v == lo:
                lo_inc = lo_inc and inc
        if c.op in ("<", "<=", "="):
            inc = c.op != "<"
            if hi is None or v < hi:
                hi, hi_inc = v, inc
            elif v == hi:
                hi_inc = hi_inc and inc
    if lo is not None and hi is not None:
        if lo > hi or (lo == hi and not (lo_inc and hi_inc)):
            return False
    candidates = []
    if lo is not None:
        if lo_inc:
            candidates.append(lo)
        if lo.prerelease is not None:
            candidates.append(Version(lo.major, lo.minor, lo.patch))
            candidates.append(Version(lo.major, lo.minor, lo.patch, lo.prerelease + ".0"))
        else:
            candidates.append(Version(lo.major, lo.minor, lo.patch + 1))
    else:
        candidates.append(Version(0, 0, 0))
    if hi is not None:
        if hi_inc:
            candidates.append(hi)
        if hi.prerelease is None:
            candidates.append(Version(hi.major, hi.minor, hi.patch, "0"))
    for c in comparators:
        if c.op == "!=":
            v = c.version
            candidates.append(Version(v.major, v.minor, v.patch + 1))
            candidates.append(Version(v.major, v.minor + 1, 0))
    return any(ba.matches(v) and bb.matches(v) for v in candidates)


def overlaps(a, b):
    """判断两个区间是否存在同时满足的版本。"""
    ra, rb = parse_range(a), parse_range(b)
    return any(
        _branches_overlap(ba, bb) for ba in ra.branches for bb in rb.branches
    )
