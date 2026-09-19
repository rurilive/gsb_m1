"""npm 风格的版本区间：解析、匹配与最高版本挑选。

区间文本由 ``||`` 分隔的 OR 分支组成，每个分支内空格分隔的比较子取 AND。
解析期把 ``^`` / ``~`` / 通配符展开成 ``< <= > >= = !=`` 的原始比较子。
"""

import re

from .version import Version, parse_version

_PRE_ID = r"(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
_BUILD_ID = r"[0-9a-zA-Z-]+"
_COMPARATOR_RE = re.compile(
    r"^(?P<op>\^|~|>=|<=|!=|>|<|=)?"
    r"(?P<major>\d+|[xX*])"
    r"(?:\.(?P<minor>\d+|[xX*]))?"
    r"(?:\.(?P<patch>\d+|[xX*]))?"
    r"(?:-(?P<pre>" + _PRE_ID + r"(?:\." + _PRE_ID + r")*))?"
    r"(?:\+" + _BUILD_ID + r"(?:\." + _BUILD_ID + r")*)?$"
)

_WILDCARDS = frozenset("xX*")


class Comparator:
    """一个原始比较子：op 是 < <= > >= = != 之一，version 是 Version。"""

    __slots__ = ("op", "version")

    def __init__(self, op, version):
        self.op = op
        self.version = version

    def __repr__(self):
        return f"Comparator({self.op}{self.version})"

    def test(self, v):
        if self.op == "<":
            return v < self.version
        if self.op == "<=":
            return v <= self.version
        if self.op == ">":
            return v > self.version
        if self.op == ">=":
            return v >= self.version
        if self.op == "=":
            return v == self.version
        return v != self.version


class _Branch:
    """一个 OR 分支：比较子取 AND，并记录显式带 prerelease 的 x.y.z 元组。"""

    __slots__ = ("comparators", "pre_tuples")

    def __init__(self, comparators, pre_tuples):
        self.comparators = comparators
        self.pre_tuples = pre_tuples

    def matches(self, v):
        if v.prerelease is not None and (v.major, v.minor, v.patch) not in self.pre_tuples:
            return False
        return all(c.test(v) for c in self.comparators)


class Range:
    """解析后的区间：OR 分支的列表，任一分支满足即满足。"""

    def __init__(self, branches):
        self.branches = branches

    def __repr__(self):
        return f"Range({self.branches!r})"

    def match(self, version):
        v = version if isinstance(version, Version) else parse_version(version)
        return any(b.matches(v) for b in self.branches)

    def __contains__(self, version):
        return self.match(version)


def _expand(token):
    """把一个比较子词元展开成 (原始比较子列表, prerelease 元组或 None)。"""
    m = _COMPARATOR_RE.match(token)
    if not m:
        raise ValueError(f"非法的比较子: {token!r}")
    op = m.group("op")
    raw = [m.group("major"), m.group("minor"), m.group("patch")]
    pre = m.group("pre")

    seen_wild = False
    for s in raw:
        if s is None or s in _WILDCARDS:
            seen_wild = True
        elif seen_wild:
            raise ValueError(f"通配段之后不能再出现数字段: {token!r}")

    first_wild = next(
        (i for i, s in enumerate(raw) if s is not None and s in _WILDCARDS), None
    )
    if pre is not None and (first_wild is not None or any(s is None for s in raw)):
        raise ValueError(f"带 prerelease 的比较子必须写全 x.y.z: {token!r}")

    if first_wild is not None:
        if op not in (None, "="):
            raise ValueError(f"通配符只能单独使用或配合 =: {token!r}")
        if first_wild == 0:
            return [], None
        nums = [int(s) if s is not None and s not in _WILDCARDS else 0 for s in raw]
        low = Version(*nums)
        high_nums = nums[:]
        high_nums[first_wild - 1] += 1
        for i in range(first_wild, 3):
            high_nums[i] = 0
        return [Comparator(">=", low), Comparator("<", Version(*high_nums))], None

    nums = [int(s) if s is not None else 0 for s in raw]
    specified = [s is not None for s in raw]
    base = Version(*nums, prerelease=pre)
    pre_tuple = tuple(nums) if pre is not None else None

    if op in (None, "=", "!=", "<", "<=", ">", ">="):
        return [Comparator(op or "=", base)], pre_tuple

    if op == "^":
        if nums[0] > 0:
            upper = (nums[0] + 1, 0, 0)
        elif nums[1] > 0:
            upper = (0, nums[1] + 1, 0)
        elif nums[2] > 0:
            upper = (0, 0, nums[2] + 1)
        elif specified[2]:
            upper = (0, 0, 1)
        elif specified[1]:
            upper = (0, 1, 0)
        else:
            upper = (1, 0, 0)
        return [Comparator(">=", base), Comparator("<", Version(*upper))], pre_tuple

    # op == "~"
    if not specified[1]:
        upper = (nums[0] + 1, 0, 0)
    else:
        upper = (nums[0], nums[1] + 1, 0)
    return [Comparator(">=", base), Comparator("<", Version(*upper))], pre_tuple


def parse_range(text):
    """解析区间文本为 Range；非法输入抛 ValueError。

    空串视为匹配任意版本（prerelease 仍默认排除）。
    """
    if isinstance(text, Range):
        return text
    if not isinstance(text, str):
        raise ValueError(f"区间必须是字符串: {text!r}")
    text = text.strip()
    if not text:
        return Range([_Branch([], frozenset())])
    branches = []
    for part in text.split("||"):
        part = part.strip()
        if not part:
            raise ValueError(f"空的 OR 分支: {text!r}")
        comparators = []
        pre_tuples = set()
        for token in part.split():
            comps, pre_tuple = _expand(token)
            comparators.extend(comps)
            if pre_tuple is not None:
                pre_tuples.add(pre_tuple)
        branches.append(_Branch(comparators, frozenset(pre_tuples)))
    return Range(branches)


def match(version, range):
    """判断 version 是否满足区间；两个参数都接受对象或字符串。"""
    r = range if isinstance(range, Range) else parse_range(range)
    return r.match(version)


def best(versions, range):
    """返回满足区间的最高 Version；没有满足者时返回 None。"""
    r = range if isinstance(range, Range) else parse_range(range)
    winner = None
    for item in versions:
        v = item if isinstance(item, Version) else parse_version(item)
        if r.match(v) and (winner is None or winner < v):
            winner = v
    return winner
