"""npm 风格的版本区间：解析、匹配、求交、化简。

区间 = `||` 分隔的 OR 分支；分支内空格分隔的比较子取 AND。
支持 `^` / `~`（含 0.x 特例）、`1.x` / `1.2.x` 通配、缺省补 `.0`、`!=` 排除。
prerelease 默认不匹配，除非同一 OR 分支里有比较子对同一 x.y.z 显式带它。
"""

import re

from .version import Version, parse_version

_OPS = ("<=", ">=", "!=", "==", "<", ">", "=", "~", "^")

_TOKEN_RE = re.compile(
    r"^v?(0|[1-9]\d*|x|X|\*)?(?:\.(0|[1-9]\d*|x|X|\*))?(?:\.(0|[1-9]\d*|x|X|\*))?"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*)?$"
)


class Comparator:
    """单个比较子，如 ``>=1.2.0``。"""

    __slots__ = ("op", "version")

    def __init__(self, op, version):
        self.op = op
        self.version = version

    def __repr__(self):
        return f"Comparator({self.op}{self.version})"

    def __str__(self):
        if self.op == "=":
            return str(self.version)
        return f"{self.op}{self.version}"

    def test(self, v):
        if self.op == "=":
            return v == self.version
        if self.op == "!=":
            return v != self.version
        if self.op == "<":
            return v < self.version
        if self.op == "<=":
            return v <= self.version
        if self.op == ">":
            return v > self.version
        return v >= self.version


class Range:
    """一个区间：OR 分支的元组，每个分支是 Comparator 元组（AND）。"""

    __slots__ = ("branches",)

    def __init__(self, branches):
        self.branches = tuple(branches)

    def __repr__(self):
        return f"Range({str(self)!r})"

    def __str__(self):
        return " || ".join(
            " ".join(str(c) for c in branch) or "*" for branch in self.branches
        )


def _num(text):
    if text is None or text in ("x", "X", "*"):
        return None
    return int(text)


def _expand_token(token):
    """把单个 token 展开为一组 Comparator（npm 语义）。"""
    op = ""
    for candidate in _OPS:
        if token.startswith(candidate):
            op = candidate
            token = token[len(candidate):]
            break
    m = _TOKEN_RE.match(token)
    if not m:
        raise ValueError(f"不是合法的区间比较子: {op}{token!r}")
    major, minor, patch = (_num(m.group(i)) for i in (1, 2, 3))
    prerelease = m.group(4)
    if prerelease and (major is None or minor is None or patch is None):
        raise ValueError(f"通配版本不能带 prerelease: {op}{token!r}")
    if op in ("", "=="):
        op = "="

    if major is None:
        if op in ("", "=", "~", "^"):
            # * / 空串：任意版本；~* 与 ^* 等价于 >=0.0.0
            if op in ("~", "^"):
                return [Comparator(">=", Version(0, 0, 0))]
            return []
        raise ValueError(f"比较运算符不能配通配符: {op}{token!r}")

    if op in ("<", "<=", ">", ">=", "!="):
        # 缺省补 .0
        return [Comparator(op, Version(major, minor or 0, patch or 0,
                                       prerelease=prerelease))]

    if op == "=":
        if patch is not None:
            return [Comparator("=", Version(major, minor, patch,
                                            prerelease=prerelease))]
        if minor is not None:
            return [Comparator(">=", Version(major, minor, 0)),
                    Comparator("<", Version(major, minor + 1, 0))]
        return [Comparator(">=", Version(major, 0, 0)),
                Comparator("<", Version(major + 1, 0, 0))]

    if op == "~":
        if minor is None:
            return [Comparator(">=", Version(major, 0, 0)),
                    Comparator("<", Version(major + 1, 0, 0))]
        lower = Version(major, minor, patch or 0, prerelease=prerelease)
        return [Comparator(">=", lower),
                Comparator("<", Version(major, minor + 1, 0))]

    # op == "^"
    if minor is None:
        if major == 0:
            return [Comparator(">=", Version(0, 0, 0)),
                    Comparator("<", Version(1, 0, 0))]
        return [Comparator(">=", Version(major, 0, 0)),
                Comparator("<", Version(major + 1, 0, 0))]
    if patch is None:
        if major == 0:
            return [Comparator(">=", Version(0, minor, 0)),
                    Comparator("<", Version(0, minor + 1, 0))]
        return [Comparator(">=", Version(major, minor, 0)),
                Comparator("<", Version(major + 1, 0, 0))]
    lower = Version(major, minor, patch, prerelease=prerelease)
    if major > 0:
        upper = Version(major + 1, 0, 0)
    elif minor > 0:
        upper = Version(0, minor + 1, 0)
    else:
        upper = Version(0, 0, patch + 1)
    return [Comparator(">=", lower), Comparator("<", upper)]


def parse_range(text):
    """解析区间字符串为 Range；非法输入抛 ValueError。

    空串等价于 ``*``（匹配任意正式版）。
    """
    if isinstance(text, Range):
        return text
    if not isinstance(text, str):
        raise ValueError(f"区间必须是字符串: {text!r}")
    text = text.strip()
    if not text:
        return Range([()])
    branches = []
    for part in text.split("||"):
        comparators = []
        for token in part.split():
            comparators.extend(_expand_token(token))
        branches.append(tuple(comparators))
    return Range(branches)


def _match_branch(version, branch):
    for comparator in branch:
        if not comparator.test(version):
            return False
    if version.prerelease:
        triple = (version.major, version.minor, version.patch)
        for comparator in branch:
            cv = comparator.version
            if cv.prerelease and (cv.major, cv.minor, cv.patch) == triple:
                return True
        return False
    return True


def match(version, rng):
    """判断版本是否落在区间内。参数接受 Version/字符串、Range/字符串。"""
    v = version if isinstance(version, Version) else parse_version(version)
    r = rng if isinstance(rng, Range) else parse_range(rng)
    return any(_match_branch(v, branch) for branch in r.branches)


def best(versions, rng):
    """满足区间的版本中取最高者；没有则返回 None。"""
    r = rng if isinstance(rng, Range) else parse_range(rng)
    found = None
    for item in versions:
        v = item if isinstance(item, Version) else parse_version(item)
        if match(v, r) and (found is None or found < v):
            found = v
    return found


def _satisfiable(branch_a, branch_b):
    """两分支的交集是否存在版本（构造候选点判定，门控按各自分支）。"""
    comparators = branch_a + branch_b
    candidates = [Version(0, 0, 0)]
    lows, highs, neqs = [], [], []
    pre_tuples = set()
    for c in comparators:
        v = c.version
        if c.op in (">", ">="):
            lows.append((v, c.op == ">="))
        elif c.op in ("<", "<="):
            highs.append((v, c.op == "<="))
        elif c.op == "=":
            candidates.append(v)
        else:
            neqs.append(v)
        if v.prerelease:
            pre_tuples.add((v.major, v.minor, v.patch))
    for v, inclusive in lows:
        if inclusive:
            candidates.append(v)
        candidates.append(Version(v.major, v.minor, v.patch))
        candidates.append(Version(v.major, v.minor, v.patch + 1))
        candidates.append(Version(v.major, v.minor + 1, 0))
        candidates.append(Version(v.major + 1, 0, 0))
        if v.prerelease:
            # 严格大于 v 的最小预发布
            candidates.append(Version(v.major, v.minor, v.patch,
                                      prerelease=v.prerelease + ".0"))
    for v, inclusive in highs:
        if inclusive:
            candidates.append(v)
        candidates.append(Version(v.major, v.minor, v.patch))
        if v.patch > 0:
            candidates.append(Version(v.major, v.minor, v.patch - 1))
        if v.minor > 0:
            candidates.append(Version(v.major, v.minor - 1, 0))
        if v.major > 0:
            candidates.append(Version(v.major - 1, 0, 0))
    for v in neqs:
        candidates.append(Version(v.major, v.minor, v.patch + 1))
    for triple in pre_tuples:
        candidates.append(Version(*triple, prerelease="0"))
    return any(
        _match_branch(c, branch_a) and _match_branch(c, branch_b)
        for c in candidates
    )


def overlaps(a, b):
    """判断两个区间是否存在同时满足的版本。"""
    ra, rb = parse_range(a), parse_range(b)
    return any(
        _satisfiable(ba, bb) for ba in ra.branches for bb in rb.branches
    )


def _as_interval(branch):
    """纯 release 且无 != 的分支转成 (lo, lo_inc, hi, hi_inc)；否则返回 None。

    空分支（任意版本）为 (None, True, None, True)；不可满足返回 False。
    """
    lo = lo_inc = hi = hi_inc = None
    for c in branch:
        if c.op == "!=" or c.version.prerelease:
            return None
        v = c.version
        if c.op in (">", ">="):
            inc = c.op == ">="
            if lo is None or v > lo or (v == lo and lo_inc and not inc):
                lo, lo_inc = v, inc
            elif v == lo:
                lo_inc = lo_inc and inc
        elif c.op in ("<", "<="):
            inc = c.op == "<="
            if hi is None or v < hi or (v == hi and hi_inc and not inc):
                hi, hi_inc = v, inc
            elif v == hi:
                hi_inc = hi_inc and inc
        else:  # "="
            if lo is None or v > lo:
                lo, lo_inc = v, True
            if hi is None or v < hi:
                hi, hi_inc = v, True
    if lo is not None and hi is not None:
        if lo > hi or (lo == hi and not (lo_inc and hi_inc)):
            return False
    return (lo, lo_inc if lo is not None else True,
            hi, hi_inc if hi is not None else True)


def _touches(cur, nxt):
    """两区间重叠或相邻（相邻时端点至少一侧闭，保证并集连续）。"""
    _, _, cur_hi, cur_hi_inc = cur
    nxt_lo, nxt_lo_inc, _, _ = nxt
    if cur_hi is None or nxt_lo is None:
        return True
    if cur_hi > nxt_lo:
        return True
    return cur_hi == nxt_lo and (cur_hi_inc or nxt_lo_inc)


def _union(cur, nxt):
    cur_lo, cur_lo_inc, cur_hi, cur_hi_inc = cur
    nxt_lo, nxt_lo_inc, nxt_hi, nxt_hi_inc = nxt
    if cur_lo is not None and nxt_lo is not None and cur_lo == nxt_lo:
        cur_lo_inc = cur_lo_inc or nxt_lo_inc
    if cur_hi is None or nxt_hi is None:
        hi, hi_inc = None, True
    elif nxt_hi > cur_hi:
        hi, hi_inc = nxt_hi, nxt_hi_inc
    elif nxt_hi < cur_hi:
        hi, hi_inc = cur_hi, cur_hi_inc
    else:
        hi, hi_inc = cur_hi, cur_hi_inc or nxt_hi_inc
    return (cur_lo, cur_lo_inc, hi, hi_inc)


def _serialize_interval(interval):
    lo, lo_inc, hi, hi_inc = interval
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
    """把区间化简为最简式字符串：重叠或相邻的 OR 分支合并。

    只合并纯 release、无 ``!=`` 的分支（含 prerelease/!= 的分支原样保留），
    因此合并前后 match 的结果集严格一致。
    """
    r = parse_range(rng)
    intervals, kept = [], []
    for branch in r.branches:
        interval = _as_interval(branch)
        if interval is None:
            kept.append(" ".join(str(c) for c in branch) or "*")
        elif interval is not False:
            intervals.append(interval)
    intervals.sort(key=lambda iv: (iv[0] is not None,
                                   iv[0]._key() if iv[0] else ()))
    merged = []
    for interval in intervals:
        if merged and _touches(merged[-1], interval):
            merged[-1] = _union(merged[-1], interval)
        else:
            merged.append(interval)
    parts = [_serialize_interval(iv) for iv in merged] + kept
    if not parts:
        # 所有分支都不可满足：用空区间表示
        return "<0.0.0"
    return " || ".join(parts)
