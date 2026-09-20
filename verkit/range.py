"""npm 风格的版本区间解析与匹配。

区间语法（空格 = AND，``||`` = OR）：

- ``^`` / ``~``：npm 语义，含 0.x 特例（``^0.1.2`` 锁定 ``0.1.*`` 等）；
- ``>=`` / ``<=`` / ``>`` / ``<`` / ``=``：比较子；
- ``!=``：精确排除一个完整版本；
- ``1.x`` / ``1.2.x`` / ``x``：通配；缺省段补 ``.0``（``1.2`` 即 ``1.2.0``）。

prerelease 默认不匹配任何区间，除非该 OR 分支里存在比较子显式带同一
``major.minor.patch`` 的 prerelease（npm 的 allow 规则）。
"""

import re

from verkit.version import Version, compare, parse_version

_OP_RE = re.compile(r"^(\^|~|>=|<=|!=|>|<|=)?([\s\S]*)$")
_NUM_RE = re.compile(r"^(0|[1-9][0-9]*)$")
_WILDCARDS = frozenset({"x", "X", "*"})


class Comparator:
    """单个比较子。``op == "*"`` 且 ``version is None`` 表示 ANY。"""

    __slots__ = ("op", "version")

    def __init__(self, op, version):
        self.op = op
        self.version = version

    def __repr__(self):
        if self.op == "*":
            return "Comparator('*')"
        return f"Comparator({self.op!r}, {str(self.version)!r})"

    def __eq__(self, other):
        if not isinstance(other, Comparator):
            return NotImplemented
        return self.op == other.op and self.version == other.version

    def __hash__(self):
        return hash((self.op, self.version))


class Range:
    """解析后的版本区间：若干 OR 分支，每分支是 AND 比较子序列。"""

    def __init__(self, raw, branches):
        self.raw = raw
        self.branches = tuple(tuple(branch) for branch in branches)

    def __repr__(self):
        return f"Range({self.raw!r})"

    def __str__(self):
        return self.raw

    def __eq__(self, other):
        if not isinstance(other, Range):
            return NotImplemented
        return self.branches == other.branches

    def __hash__(self):
        return hash(self.branches)

    def matches(self, version):
        """判断版本对象是否落在区间内。"""
        return _matches_branches(version, self.branches)


def parse_range(text):
    """解析区间文本，返回 :class:`Range`；非法输入抛 ValueError。"""
    if isinstance(text, Range):
        return text
    if not isinstance(text, str):
        raise ValueError(f"区间必须是字符串: {text!r}")
    raw = text.strip()
    if not raw:
        raise ValueError("区间不能为空字符串")

    branches = []
    for branch_text in raw.split("||"):
        tokens = branch_text.split()
        if not tokens:
            raise ValueError(f"区间存在空的 OR 分支: {text!r}")
        branch = []
        for token in tokens:
            branch.extend(_compile_token(token, text))
        branches.append(tuple(branch))
    return Range(raw, branches)


def match(version, range_spec):
    """版本（字符串或 Version）是否满足区间（字符串或 Range）。"""
    if not isinstance(version, Version):
        version = parse_version(version)
    range_obj = range_spec if isinstance(range_spec, Range) else parse_range(range_spec)
    return _matches_branches(version, range_obj.branches)


def best(versions, range_spec):
    """候选中满足区间的最高优先级版本；没有则返回 None。"""
    range_obj = range_spec if isinstance(range_spec, Range) else parse_range(range_spec)
    winner = None
    winner_key = None
    for item in versions:
        candidate = item if isinstance(item, Version) else parse_version(item)
        if not _matches_branches(candidate, range_obj.branches):
            continue
        key = candidate._key()
        if winner is None or key > winner_key:
            winner = candidate
            winner_key = key
    return winner


def _matches_branches(version, branches):
    core = (version.major, version.minor, version.patch)
    is_pre = version.prerelease is not None
    for branch in branches:
        if not all(_test_comparator(comparator, version) for comparator in branch):
            continue
        if is_pre and not _prerelease_allowed(branch, core):
            continue
        return True
    return False


def _prerelease_allowed(branch, core):
    """该 AND 分支里是否有比较子对同一 x.y.z 显式带 prerelease。"""
    for comparator in branch:
        ref = comparator.version
        if ref is None or ref.prerelease is None:
            continue
        if (ref.major, ref.minor, ref.patch) == core:
            return True
    return False


def _test_comparator(comparator, version):
    if comparator.op == "*":
        return True
    result = compare(version, comparator.version)
    if comparator.op == "==":
        return result == 0
    if comparator.op == "!=":
        return result != 0
    if comparator.op == ">":
        return result > 0
    if comparator.op == ">=":
        return result >= 0
    if comparator.op == "<":
        return result < 0
    if comparator.op == "<=":
        return result <= 0
    raise ValueError(f"未知比较子: {comparator.op!r}")


def _compile_token(token, whole_text):
    """把单个比较子文本编译成 AND Comparator 元组。"""
    match_op = _OP_RE.match(token)
    op = match_op.group(1)
    rest = match_op.group(2)
    if not rest:
        raise ValueError(f"区间比较子缺少版本号: {token!r}（来自 {whole_text!r}）")

    build = None
    if "+" in rest:
        rest, build = rest.split("+", 1)
        if not build or "+" in build:
            raise ValueError(f"非法 build 元数据: {token!r}")
    prerelease = None
    if "-" in rest:
        rest, prerelease = rest.split("-", 1)
        if not prerelease:
            raise ValueError(f"非法 prerelease: {token!r}")

    pieces = rest.split(".")
    if not 1 <= len(pieces) <= 3 or any(piece == "" for piece in pieces):
        raise ValueError(f"非法区间比较子: {token!r}")

    numbers = []
    wildcard_at = None
    for index, piece in enumerate(pieces):
        if piece in _WILDCARDS:
            if wildcard_at is None:
                wildcard_at = index
            numbers.append(None)
        else:
            if wildcard_at is not None or not _NUM_RE.match(piece):
                raise ValueError(f"非法区间比较子: {token!r}")
            numbers.append(int(piece))

    if wildcard_at is not None and (prerelease is not None or build is not None):
        raise ValueError(f"通配段不能带 prerelease/build: {token!r}")
    if op not in (None, "=", "^", "~") and wildcard_at is not None:
        raise ValueError(f"比较运算符不能与通配段组合: {token!r}")

    pad_none = wildcard_at is not None or op in ("^", "~")
    full = wildcard_at is None and (len(pieces) == 3 or op not in ("^", "~"))
    if not full and (prerelease is not None or build is not None):
        raise ValueError(f"prerelease/build 要求完整三段版本号: {token!r}")
    while len(numbers) < 3:
        numbers.append(None if pad_none else 0)
    major, minor, patch = numbers

    if full:
        suffix = ""
        if prerelease is not None:
            suffix += "-" + prerelease
        if build is not None:
            suffix += "+" + build
        version = parse_version(f"{major}.{minor}.{patch}{suffix}")
    else:
        version = None

    if op == "^":
        return _caret(major, minor, patch, version)
    if op == "~":
        return _tilde(major, minor, patch, version)
    if wildcard_at is not None:
        return _xrange(major, minor)
    if op in (">", ">=", "<", "<=", "!="):
        return (Comparator(op, version),)
    return (Comparator("==", version),)


def _v(major, minor, patch, prerelease=None):
    return Version(major, minor, patch, prerelease=prerelease)


def _xrange(major, minor):
    """``M.x`` / ``M.m.x`` / ``*`` 展开成半开区间。"""
    if major is None:
        return (Comparator("*", None),)
    if minor is None:
        return (
            Comparator(">=", _v(major, 0, 0)),
            Comparator("<", _v(major + 1, 0, 0)),
        )
    return (
    Comparator(">=", _v(major, minor, 0)),
    Comparator("<", _v(major, minor + 1, 0)),
)


def _caret(major, minor, patch, version):
    """npm caret：最左非零段锁定；0.x / 0.0.x 逐级收窄。"""
    if major is None:
        return (Comparator("*", None),)
    if minor is None:
        upper = _v(major + 1, 0, 0)
        lower = _v(major, 0, 0)
    elif patch is None:
        upper = _v(major + 1, 0, 0) if major > 0 else _v(0, minor + 1, 0)
        lower = _v(major, minor, 0)
    else:
        if major > 0:
            upper = _v(major + 1, 0, 0)
        elif minor > 0:
            upper = _v(0, minor + 1, 0)
        else:
            upper = _v(0, 0, patch + 1)
        lower = version
    return (Comparator(">=", lower), Comparator("<", upper))


def _tilde(major, minor, patch, version):
    """npm tilde：允许 patch 级变动；未给 minor 时允许 minor 级变动。"""
    if major is None:
        return (Comparator("*", None),)
    if minor is None:
        return (
            Comparator(">=", _v(major, 0, 0)),
            Comparator("<", _v(major + 1, 0, 0)),
        )
    if patch is None:
        lower = _v(major, minor, 0)
    else:
        lower = version
    return (
        Comparator(">=", lower),
        Comparator("<", _v(major, minor + 1, 0)),
    )
