"""版本区间（range）的解析、匹配与择优。

语法（npm semver 的常用子集）：

- 比较子：``<`` ``<=`` ``>`` ``>=`` ``=`` ``!=`` 加版本；裸版本等价于 ``=``
- 缺省段补 ``.0``：``>=1.2`` 即 ``>=1.2.0``，裸 ``1.2`` 即 ``=1.2.0``
- 通配：``1.x`` / ``1.2.*`` 展开为 ``>=低位 <次位进一``；``*`` 匹配任意
- ``^`` / ``~`` 按 npm 语义（含 0.x 特例）
- 空格分隔为 AND，``||`` 为 OR
- prerelease 默认不被匹配，除非同一 OR 分支里有比较子对相同的
  x.y.z 显式带了 prerelease
"""

import re

from .version import Version, compare, parse_version

_SEG = r"(?:0|[1-9]\d*|x|X|\*)"
_TOKEN_RE = re.compile(
    rf"^(?P<op><=|>=|!=|<|>|=)?"
    rf"(?P<major>{_SEG})"
    rf"(?:\.(?P<minor>{_SEG}))?"
    rf"(?:\.(?P<patch>{_SEG}))?"
    rf"(?:-(?P<pre>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    rf"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
_WILD = frozenset("xX*")


class _Comparator:
    """单个比较子：运算符 + 精确版本。"""

    __slots__ = ("op", "version")

    def __init__(self, op, version):
        self.op = op
        self.version = version

    def test(self, v):
        c = compare(v, self.version)
        return {
            "<": c < 0,
            "<=": c <= 0,
            ">": c > 0,
            ">=": c >= 0,
            "=": c == 0,
            "!=": c != 0,
        }[self.op]

    def __repr__(self):
        return f"_Comparator({self.op}{self.version})"


def _make_version(major, minor, patch, pre=None):
    text = f"{major}.{minor}.{patch}" + (f"-{pre}" if pre else "")
    return parse_version(text)  # 复用严格校验


def _segments(m):
    """把正则匹配到的三段拆成 (数值或 None, 是否显式通配)。"""
    out = []
    for name in ("major", "minor", "patch"):
        seg = m.group(name)
        if seg is None:
            out.append((None, False))
        elif seg in _WILD:
            out.append((None, True))
        else:
            out.append((int(seg), False))
    return out


def _expand_caret(segs, pre):
    (major, _), (minor, _), (patch, _) = segs
    if major is None:
        return []
    lo = _make_version(major, minor or 0, patch or 0, pre)
    if major > 0 or minor is None:
        hi = _make_version(major + 1, 0, 0)
    elif minor > 0 or patch is None:
        hi = _make_version(0, minor + 1, 0)
    else:
        hi = _make_version(0, 0, patch + 1)
    return [_Comparator(">=", lo), _Comparator("<", hi)]


def _expand_tilde(segs, pre):
    (major, _), (minor, _), (patch, _) = segs
    if major is None:
        return []
    lo = _make_version(major, minor or 0, patch or 0, pre)
    if minor is None:
        hi = _make_version(major + 1, 0, 0)
    else:
        hi = _make_version(major, minor + 1, 0)
    return [_Comparator(">=", lo), _Comparator("<", hi)]


def _expand_plain(op, segs, pre):
    (major, major_wild), (minor, minor_wild), (patch, patch_wild) = segs
    if pre and (major_wild or minor_wild or patch_wild):
        raise ValueError("通配符不能和 prerelease 一起用")
    if op == "!=":
        if major_wild or minor_wild or patch_wild:
            raise ValueError("!= 只支持精确版本，不支持通配符")
        return [_Comparator("!=", _make_version(major or 0, minor or 0, patch or 0, pre))]
    if op in (None, "="):
        if major is None:
            return []  # * / x：匹配任意
        if minor is None:
            if minor_wild:  # 1.x -> >=1.0.0 <2.0.0
                return [
                    _Comparator(">=", _make_version(major, 0, 0)),
                    _Comparator("<", _make_version(major + 1, 0, 0)),
                ]
            return [_Comparator("=", _make_version(major, 0, 0, pre))]
        if patch is None:
            if patch_wild:  # 1.2.x -> >=1.2.0 <1.3.0
                return [
                    _Comparator(">=", _make_version(major, minor, 0)),
                    _Comparator("<", _make_version(major, minor + 1, 0)),
                ]
            return [_Comparator("=", _make_version(major, minor, 0, pre))]
        return [_Comparator("=", _make_version(major, minor, patch, pre))]
    # 不等式里的通配段按缺省处理，补 0
    return [_Comparator(op, _make_version(major or 0, minor or 0, patch or 0, pre))]


def _expand_token(token):
    if token[0] in "^~":
        m = _TOKEN_RE.match(token[1:])
        if not m or m.group("op"):
            raise ValueError(f"无法解析的比较子: {token!r}")
        expand = _expand_caret if token[0] == "^" else _expand_tilde
        return expand(_segments(m), m.group("pre"))
    m = _TOKEN_RE.match(token)
    if not m:
        raise ValueError(f"无法解析的比较子: {token!r}")
    return _expand_plain(m.group("op"), _segments(m), m.group("pre"))


def _match_set(v, comparators):
    if not all(c.test(v) for c in comparators):
        return False
    if not v.prerelease:
        return True
    # prerelease 只在同分支有比较子对同一 x.y.z 显式带 prerelease 时放行
    return any(
        c.version.prerelease
        and (c.version.major, c.version.minor, c.version.patch)
        == (v.major, v.minor, v.patch)
        for c in comparators
    )


class Range:
    """解析后的区间：若干 OR 分支，每支是一组 AND 的比较子。"""

    def __init__(self, sets):
        self._sets = sets

    def match(self, version):
        v = version if isinstance(version, Version) else parse_version(version)
        return any(_match_set(v, s) for s in self._sets)

    def __repr__(self):
        branches = [" ".join(f"{c.op}{c.version}" for c in s) for s in self._sets]
        return f"Range({' || '.join(branches)!r})"


def parse_range(text):
    """解析区间文本，返回 Range；非法输入抛 ValueError。

    空串与 ``*`` 匹配任意版本（仍受 prerelease 规则约束）。
    """
    if isinstance(text, Range):
        return text
    if not isinstance(text, str):
        raise ValueError(f"区间必须是字符串: {text!r}")
    text = text.strip()
    if not text:
        return Range([[]])
    sets = []
    for branch in text.split("||"):
        comparators = []
        for token in branch.split():
            comparators.extend(_expand_token(token))
        sets.append(comparators)
    return Range(sets)


def match(version, range_spec):
    """判断 version 是否满足区间；两者都接受字符串或已解析对象。"""
    return parse_range(range_spec).match(version)


def best(versions, range_spec):
    """返回满足区间的最高 Version；无满足者返回 None。"""
    r = parse_range(range_spec)
    winner = None
    for item in versions:
        v = item if isinstance(item, Version) else parse_version(item)
        if r.match(v) and (winner is None or winner < v):
            winner = v
    return winner
