"""版本区间（range）的解析与匹配。

语法对齐 npm semver 的常用子集：

- 比较子：``>=`` ``<=`` ``>`` ``<`` ``=`` ``!=``，缺省为 ``=``；缺省段补 ``.0``
- ``^`` / ``~``：兼容区间，含 0.x 特例
- ``x`` / ``X`` / ``*``：通配段
- 空格分隔为 AND，``||`` 为 OR
- 带 prerelease 的版本默认不匹配，除非该 OR 分支里有比较子
  对同一 x.y.z 显式带了 prerelease
"""

import re

from .version import Version, compare, parse_version

_SEGMENT = r"(?:0|[1-9]\d*|[xX*])"
_PARTIAL_RE = re.compile(
    r"^(?P<major>" + _SEGMENT + r")"
    r"(?:\.(?P<minor>" + _SEGMENT + r"))?"
    r"(?:\.(?P<patch>" + _SEGMENT + r"))?"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*)?$"
)
_TOKEN_RE = re.compile(r"^(?P<op>\^|~|>=|<=|!=|>|<|=)?(?P<body>.*)$")

_WILD = object()

_OPS = {
    ">": lambda c: c > 0,
    ">=": lambda c: c >= 0,
    "<": lambda c: c < 0,
    "<=": lambda c: c <= 0,
    "=": lambda c: c == 0,
    "!=": lambda c: c != 0,
}


class _Comparator:
    """单个比较子：运算符 + 完整版本。"""

    __slots__ = ("op", "version")

    def __init__(self, op, version):
        self.op = op
        self.version = version

    def test(self, version):
        return _OPS[self.op](compare(version, self.version))

    def __repr__(self):
        return f"_Comparator({self.op!r}, {str(self.version)!r})"


class Range:
    """解析后的区间：OR 分支的元组，每个分支是比较子元组（AND）。"""

    def __init__(self, branches):
        self.branches = branches

    def __repr__(self):
        return f"Range({self.branches!r})"

    def match(self, version):
        """判断版本是否满足区间；接受 Version 或 semver 字符串。"""
        v = version if isinstance(version, Version) else parse_version(version)
        return any(self._branch_matches(branch, v) for branch in self.branches)

    @staticmethod
    def _branch_matches(branch, version):
        if not all(c.test(version) for c in branch):
            return False
        if version.prerelease is None:
            return True
        same_core = (version.major, version.minor, version.patch)
        return any(
            c.version.prerelease is not None
            and (c.version.major, c.version.minor, c.version.patch) == same_core
            for c in branch
        )


def _segment(text):
    if text is None:
        return None
    if text in ("x", "X", "*"):
        return _WILD
    return int(text)


def _fill(segment):
    return 0 if segment is None or segment is _WILD else segment


def _expand_caret(major, minor, patch, prerelease):
    if major is None or major is _WILD:
        return ()
    lower = Version(_fill(major), _fill(minor), _fill(patch), prerelease=prerelease)
    if major > 0:
        upper = Version(major + 1, 0, 0)
    elif minor is None or minor is _WILD:
        upper = Version(1, 0, 0)
    elif minor > 0:
        upper = Version(0, minor + 1, 0)
    elif patch is None or patch is _WILD:
        upper = Version(0, 1, 0)
    else:
        upper = Version(0, 0, patch + 1)
    return (_Comparator(">=", lower), _Comparator("<", upper))


def _expand_tilde(major, minor, patch, prerelease):
    if major is None or major is _WILD:
        return ()
    lower = Version(_fill(major), _fill(minor), _fill(patch), prerelease=prerelease)
    if minor is None or minor is _WILD:
        upper = Version(major + 1, 0, 0)
    else:
        upper = Version(major, minor + 1, 0)
    return (_Comparator(">=", lower), _Comparator("<", upper))


def _expand_wildcard(op, major, minor, patch, token):
    segments = (major, minor, patch)
    first_wild = next(i for i, s in enumerate(segments) if s is _WILD)
    if first_wild == 0:
        if op in (">", "<", "!="):
            raise ValueError(f"通配段不支持该运算符: {token!r}")
        return ()
    if first_wild == 1:
        low, high = (segments[0], 0, 0), (segments[0] + 1, 0, 0)
    else:
        low = (segments[0], segments[1], 0)
        high = (segments[0], segments[1] + 1, 0)
    if op == "=":
        return (_Comparator(">=", Version(*low)), _Comparator("<", Version(*high)))
    if op == "!=":
        raise ValueError(f"!= 不支持通配段: {token!r}")
    if op == ">=":
        return (_Comparator(">=", Version(*low)),)
    if op == ">":
        return (_Comparator(">=", Version(*high)),)
    if op == "<=":
        return (_Comparator("<", Version(*high)),)
    return (_Comparator("<", Version(*low)),)


def _expand_token(token):
    m = _TOKEN_RE.match(token)
    op = m.group("op") or "="
    body = m.group("body")
    pm = _PARTIAL_RE.match(body)
    if not pm:
        raise ValueError(f"非法的区间比较子: {token!r}")
    major = _segment(pm.group("major"))
    minor = _segment(pm.group("minor"))
    patch = _segment(pm.group("patch"))
    prerelease = pm.group("prerelease")
    if op == "^":
        return _expand_caret(major, minor, patch, prerelease)
    if op == "~":
        return _expand_tilde(major, minor, patch, prerelease)
    if major is _WILD or minor is _WILD or patch is _WILD:
        if prerelease is not None:
            raise ValueError(f"通配段不能带 prerelease: {token!r}")
        return _expand_wildcard(op, major, minor, patch, token)
    version = Version(_fill(major), _fill(minor), _fill(patch), prerelease=prerelease)
    return (_Comparator(op, version),)


def parse_range(text):
    """解析区间文本为 Range，非法输入抛 ValueError。

    空串（或纯空白）等价于 ``*``，匹配一切正式版。
    """
    if isinstance(text, Range):
        return text
    if not isinstance(text, str):
        raise ValueError(f"区间必须是字符串: {text!r}")
    branches = []
    for part in text.split("||"):
        comparators = []
        for token in part.split():
            comparators.extend(_expand_token(token))
        branches.append(tuple(comparators))
    return Range(tuple(branches))


def match(version, spec):
    """判断 version 是否满足区间 spec（Range 或区间文本）。"""
    rng = spec if isinstance(spec, Range) else parse_range(spec)
    return rng.match(version)


def best(versions, spec):
    """在满足区间的版本中取优先级最高者；无命中返回 None。

    返回 Version 对象；入参可以是 Version 或 semver 字符串的混合。
    """
    rng = spec if isinstance(spec, Range) else parse_range(spec)
    hits = []
    for item in versions:
        v = item if isinstance(item, Version) else parse_version(item)
        if rng.match(v):
            hits.append(v)
    return max(hits) if hits else None
