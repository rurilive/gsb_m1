"""npm 风格的版本区间：解析、匹配、选优、重叠判断与化简。

区间文本按 ``||`` 切成 OR 分支，分支内空格分隔的比较子取 AND。
支持 ``^`` / ``~``（含 0.x 特例）、``x`` / ``*`` 通配、缺省补 ``.0``、
``!=`` 排除。带 prerelease 的版本默认不匹配，除非同一 OR 分支里有
比较子对同一个 x.y.z 显式带了 prerelease。
"""

import re

from .version import Version, parse_version

_OP_RE = re.compile(r"^(<=|>=|!=|<|>|=)?(\^|~)?(.*)$")
_PARTIAL_RE = re.compile(
    r"^([0-9]+|x|X|\*)"
    r"(?:\.([0-9]+|x|X|\*))?"
    r"(?:\.([0-9]+|x|X|\*))?"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*)?$"
)
_WILDCARDS = ("x", "X", "*")


class Comparator:
    """单个原子比较子：运算符加一个完整版本。"""

    __slots__ = ("op", "version")

    def __init__(self, op, version):
        self.op = op
        self.version = version

    def __repr__(self):
        return f"Comparator({self.op}{self.version})"


class Range:
    """解析后的区间：OR 分支列表，每个分支是 AND 的比较子列表。"""

    def __init__(self, branches, text=None):
        self.branches = branches
        self.text = text

    def __repr__(self):
        return f"Range({self.text!r})"


def _is_wildcard(part):
    return part is None or part in _WILDCARDS


def _expand_token(token):
    """把一个比较子记号展开成原子比较子列表。

    ``!=`` 带部分版本（如 ``!=1.2``）时返回 ("OR", 下界分支, 上界分支)，
    由调用方做分支拆分。
    """
    m = _OP_RE.match(token)
    op, mod, body = m.groups()
    pm = _PARTIAL_RE.match(body) if body else None
    if not pm:
        raise ValueError(f"无法解析区间比较子: {token!r}")
    major_s, minor_s, patch_s, pre = pm.groups()

    if _is_wildcard(major_s):
        level = 0
    elif _is_wildcard(minor_s):
        level = 1
    elif _is_wildcard(patch_s):
        level = 2
    else:
        level = 3
    if pre and level < 3:
        raise ValueError(f"通配版本不能带 prerelease: {token!r}")

    major = 0 if level == 0 else int(major_s)
    minor = 0 if level <= 1 else int(minor_s)
    patch = 0 if level <= 2 else int(patch_s)
    base = Version(major, minor, patch, prerelease=pre if level == 3 else None)

    if mod == "~":
        if level == 0:
            return []
        if level == 1:
            return [Comparator(">=", base), Comparator("<", Version(major + 1, 0, 0))]
        return [Comparator(">=", base), Comparator("<", Version(major, minor + 1, 0))]

    if mod == "^":
        if level == 0:
            return []
        if major > 0:
            upper = Version(major + 1, 0, 0)
        elif level >= 2 and minor > 0:
            upper = Version(0, minor + 1, 0)
        elif level == 3:
            upper = Version(0, 0, patch + 1)
        elif level == 2:
            upper = Version(0, 1, 0)
        else:
            upper = Version(1, 0, 0)
        return [Comparator(">=", base), Comparator("<", upper)]

    upper = None
    if level == 1:
        upper = Version(major + 1, 0, 0)
    elif level == 2:
        upper = Version(major, minor + 1, 0)

    if op in (None, "="):
        if level == 0:
            return []
        if level < 3:
            return [Comparator(">=", base), Comparator("<", upper)]
        return [Comparator("=", base)]
    if op == "<":
        return [Comparator("<", base)]
    if op == "<=":
        if level == 3:
            return [Comparator("<=", base)]
        return [Comparator("<", upper)]
    if op == ">":
        if level == 3:
            return [Comparator(">", base)]
        return [Comparator(">=", upper)]
    if op == ">=":
        return [Comparator(">=", base)]
    if op == "!=":
        if level == 0:
            return [Comparator("<", Version(0, 0, 0))]
        if level == 3:
            return [Comparator("!=", base)]
        return ("OR", [Comparator("<", base)], [Comparator(">=", upper)])
    raise ValueError(f"无法解析区间比较子: {token!r}")


def parse_range(text):
    """解析区间文本为 Range，非法输入抛 ValueError。

    空串与 ``*`` 等价，匹配一切正式版本。
    """
    if isinstance(text, Range):
        return text
    if not isinstance(text, str):
        raise ValueError(f"区间必须是字符串: {text!r}")
    stripped = text.strip()
    if not stripped:
        return Range([[]], text=text)
    branches = []
    for part in stripped.split("||"):
        branch_sets = [[]]
        for token in part.split():
            expanded = _expand_token(token)
            if isinstance(expanded, tuple):
                _, low_arm, high_arm = expanded
                branch_sets = (
                    [b + low_arm for b in branch_sets]
                    + [b + high_arm for b in branch_sets]
                )
            else:
                branch_sets = [b + expanded for b in branch_sets]
        branches.extend(branch_sets)
    return Range(branches, text=text)


def _satisfies(version, comparator):
    op, cv = comparator.op, comparator.version
    if op == ">=":
        return not (version < cv)
    if op == ">":
        return cv < version
    if op == "<=":
        return version < cv or version == cv
    if op == "<":
        return version < cv
    if op == "=":
        return version == cv
    return not (version == cv)  # !=


def _same_tuple(a, b):
    return (a.major, a.minor, a.patch) == (b.major, b.minor, b.patch)


def match(version, rng):
    """判断版本是否落在区间内。version 可以是 Version 或字符串。"""
    v = version if isinstance(version, Version) else parse_version(version)
    r = rng if isinstance(rng, Range) else parse_range(rng)
    for branch in r.branches:
        if not all(_satisfies(v, c) for c in branch):
            continue
        if v.prerelease and not any(
            c.version.prerelease and _same_tuple(c.version, v) for c in branch
        ):
            continue
        return True
    return False


def best(versions, rng):
    """返回满足区间的最高版本，无满足者返回 None。"""
    r = rng if isinstance(rng, Range) else parse_range(rng)
    winner = None
    for item in versions:
        v = item if isinstance(item, Version) else parse_version(item)
        if match(v, r) and (winner is None or winner < v):
            winner = v
    return winner


def _max_lo(a, b):
    if a is None:
        return b
    if b is None:
        return a
    av, ainc = a
    bv, binc = b
    if av < bv:
        return b
    if bv < av:
        return a
    return (av, ainc and binc)


def _min_hi(a, b):
    if a is None:
        return b
    if b is None:
        return a
    av, ainc = a
    bv, binc = b
    if bv < av:
        return b
    if av < bv:
        return a
    return (av, ainc and binc)


def _max_hi(a, b):
    av, ainc = a
    bv, binc = b
    if av < bv:
        return b
    if bv < av:
        return a
    return (av, ainc or binc)


def _branch_interval(branch):
    """把一个 AND 分支折算成 (下界, 上界, 排除点)。

    下界/上界是 (Version, 是否含端点) 或 None（无界）。
    """
    lo = hi = None
    neq = []
    for c in branch:
        if c.op == ">=":
            lo = _max_lo(lo, (c.version, True))
        elif c.op == ">":
            lo = _max_lo(lo, (c.version, False))
        elif c.op == "<=":
            hi = _min_hi(hi, (c.version, True))
        elif c.op == "<":
            hi = _min_hi(hi, (c.version, False))
        elif c.op == "=":
            lo = _max_lo(lo, (c.version, True))
            hi = _min_hi(hi, (c.version, True))
        else:  # !=
            neq.append(c.version)
    return lo, hi, neq


def _is_empty(lo, hi, neq=()):
    if lo is not None and hi is not None:
        lv, linc = lo
        hv, hinc = hi
        if hv < lv:
            return True
        if lv == hv:
            if not (linc and hinc):
                return True
            if any(lv == n for n in neq):
                return True
    return False


def _branches_intersect(ba, bb):
    loa, hia, neqa = _branch_interval(ba)
    lob, hib, neqb = _branch_interval(bb)
    lo = _max_lo(loa, lob)
    hi = _min_hi(hia, hib)
    return not _is_empty(lo, hi, neqa + neqb)


def overlaps(a, b):
    """判断两个区间是否存在同时满足的版本。"""
    ra = a if isinstance(a, Range) else parse_range(a)
    rb = b if isinstance(b, Range) else parse_range(b)
    return any(
        _branches_intersect(ba, bb) for ba in ra.branches for bb in rb.branches
    )


def _touches(hi, lo):
    """上一个区间的上界与下一个区间的下界是否重叠或相邻。"""
    if hi is None or lo is None:
        return True
    hv, hinc = hi
    lv, linc = lo
    if hv < lv:
        return False
    if lv < hv:
        return True
    return hinc or linc


def _render_interval(lo, hi):
    if lo is None and hi is None:
        return "*"
    if lo is not None and hi is not None and lo[0] == hi[0] and lo[1] and hi[1]:
        return str(lo[0])
    parts = []
    if lo is not None:
        parts.append((">=" if lo[1] else ">") + str(lo[0]))
    if hi is not None:
        parts.append(("<=" if hi[1] else "<") + str(hi[0]))
    return " ".join(parts)


def _render_branch(branch):
    return " ".join(
        str(c.version) if c.op == "=" else c.op + str(c.version) for c in branch
    )


def _interval_sort_key(interval):
    lo, _ = interval
    if lo is None:
        return (0, 0, 0, 0, 0)
    v, inc = lo
    return (1, v.major, v.minor, v.patch, 0 if inc else 1)


def normalize(rng):
    """把区间化简成最简式字符串：合并重叠或相邻的 OR 分支。

    只合并不含 ``!=`` 与 prerelease 比较子的纯区间分支，其余分支原样
    保留，因此化简前后 match 的结果集完全一致。
    """
    r = rng if isinstance(rng, Range) else parse_range(rng)
    intervals = []
    literals = []
    for branch in r.branches:
        lo, hi, neq = _branch_interval(branch)
        if _is_empty(lo, hi, neq):
            continue
        if neq or any(c.version.prerelease for c in branch):
            literals.append(branch)
        else:
            intervals.append((lo, hi))
    intervals.sort(key=_interval_sort_key)

    merged = []
    for lo, hi in intervals:
        if merged and _touches(merged[-1][1], lo):
            prev_lo, prev_hi = merged[-1]
            merged[-1] = (prev_lo, None if prev_hi is None or hi is None
                          else _max_hi(prev_hi, hi))
        else:
            merged.append((lo, hi))

    parts = [_render_interval(lo, hi) for lo, hi in merged]
    parts.extend(_render_branch(b) for b in literals)
    if not parts:
        return "<0.0.0"
    return " || ".join(parts)
