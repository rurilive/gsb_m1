"""版本区间（node-semver 风格）的解析与匹配。

区间文本由若干个 OR 分支组成（``||`` 分隔），每个分支是若干个用空格
分隔的比较子，空格即 AND。比较子的写法：

- ``^`` / ``~``：兼容区间，按 npm 语义展开（含 0.x 特例）
- ``>=`` / ``<=`` / ``>`` / ``<``：比较
- ``!=``：精确排除（忽略 build，按 semver 优先级相等）
- ``1.x`` / ``1.2.x`` / ``*``：通配
- 裸版本或缺省段（``1``、``1.2``）：缺省段补 ``.0``，视作精确版本

prerelease 默认不被区间匹配；只有同一 AND 分支里存在与待匹配版本
major.minor.patch 完全相同、且自身显式带 prerelease 的比较子时，
该 prerelease 版本才可能被该分支接受。
"""

import re

from verkit.version import Version, parse_version


class Range:
    """解析后的版本区间：若干 OR 分支，每支是 AND 比较子集合。"""

    def __init__(self, text, branches):
        self.text = text
        self._branches = branches

    def __repr__(self):
        return f"Range({self.text!r})"

    def __str__(self):
        return self.text


_SPEC_RE = re.compile(
    r"^(?:"
    r"(\*)"
    r"|(\d+)(?:\.(x|X|\*|\d+)(?:\.(x|X|\*|\d+))?)?"
    r")"
    r"(?:-([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)


def _parse_spec(spec):
    """解析单个比较子的操作数。

    返回 ``(segments, prerelease, build)``：segments 为至多 3 个
    int/None（None 表示 x 通配段）；整体 ``*`` 时 segments 为空。
    """
    m = _SPEC_RE.match(spec)
    if not m:
        raise ValueError(f"无法识别的版本写法: {spec!r}")
    if m.group(1):
        return [], None, None

    major_s = m.group(2)
    minor_s = m.group(3)
    patch_s = m.group(4)
    prerelease = m.group(5)
    build = m.group(6)

    if len(major_s) > 1 and major_s[0] == "0":
        raise ValueError(f"版本段不允许前导零: {spec!r}")
    segments = [int(major_s)]
    for part in (minor_s, patch_s):
        if part is None:
            break
        if part in ("x", "X", "*"):
            segments.append(None)
        else:
            if len(part) > 1 and part[0] == "0":
                raise ValueError(f"版本段不允许前导零: {spec!r}")
            segments.append(int(part))

    # 一旦出现通配段，其后不能再出现数字段（如 1.x.3 非法）。
    if None in segments and segments[-1] is not None:
        raise ValueError(f"通配段之后不能再有数字段: {spec!r}")

    if prerelease is not None and (len(segments) < 3 or None in segments):
        raise ValueError(f"prerelease 必须挂在完整的 x.y.z 上: {spec!r}")

    return segments, prerelease, build


def _v(major, minor, patch, prerelease=None):
    return Version(major, minor, patch, prerelease=prerelease)


def _expand(token):
    """把一个比较子 token 展开成 ``(comparators, pre_triples)``。

    comparator 为 ``(op, version)``；op 取
    ``=``/``!=``/``>=``/``<=``/``>``/``<``。pre_triples 是该比较子
    显式放行 prerelease 的 ``(major, minor, patch)`` 集合。
    """
    m = re.match(r"^(\^|~|>=|<=|!=|>|<|=)?(.*)$", token, re.S)
    op = m.group(1) or "="
    spec = m.group(2)
    if spec == "":
        raise ValueError(f"比较子缺少版本号: {token!r}")

    segments, prerelease, _build = _parse_spec(spec)
    comparators = []
    pre_triples = set()

    def add(cmp_op, version):
        comparators.append((cmp_op, version))

    star = len(segments) == 0
    wild = None in segments
    major = segments[0] if segments else None
    minor = segments[1] if len(segments) >= 2 else None
    patch = segments[2] if len(segments) >= 3 else None

    if op in (">=", "<=", ">", "<") and star:
        raise ValueError(f"{op} 不能搭配通配符 *: {token!r}")

    if star:
        return comparators, pre_triples  # 空比较集合：恒真

    if op == "!=":
        if wild:
            raise ValueError(f"!= 只支持精确版本: {token!r}")
        version = _v(major, minor or 0, patch or 0, prerelease)
        add("!=", version)
        if prerelease is not None:
            pre_triples.add((version.major, version.minor, version.patch))
        return comparators, pre_triples

    if op == "=":
        if wild:
            if minor is None:
                # M.x => >=M.0.0 <(M+1).0.0
                add(">=", _v(major, 0, 0))
                add("<", _v(major + 1, 0, 0))
            else:
                # M.m.x => >=M.m.0 <M.(m+1).0
                add(">=", _v(major, minor, 0))
                add("<", _v(major, minor + 1, 0))
        else:
            version = _v(major, minor or 0, patch or 0, prerelease)
            add("=", version)
            if prerelease is not None:
                pre_triples.add((version.major, version.minor, version.patch))
        return comparators, pre_triples

    if op == "^":
        if wild:
            raise ValueError(f"^ 不能搭配通配段: {token!r}")
        # 缺省段先补 .0：^1.2 == ^1.2.0，上界随 0.x 特例锁定
        mmajor, mminor, mpatch = major, minor if minor is not None else 0, patch if patch is not None else 0
        lower = _v(mmajor, mminor, mpatch, prerelease)
        add(">=", lower)
        if prerelease is not None:
            pre_triples.add((mmajor, mminor, mpatch))
        # npm caret 上界：首个非零段的下一档（0.0.x 特例：只锁补丁档）
        if mmajor > 0:
            upper = _v(mmajor + 1, 0, 0)
        elif mminor > 0:
            upper = _v(0, mminor + 1, 0)
        else:
            upper = _v(0, 0, mpatch + 1)
        add("<", upper)
        return comparators, pre_triples

    if op == "~":
        if wild:
            if minor is None:
                # ~M.x => >=M.0.0 <(M+1).0.0
                add(">=", _v(major, 0, 0))
                add("<", _v(major + 1, 0, 0))
            else:
                # ~M.m.x => >=M.m.0 <M.(m+1).0
                add(">=", _v(major, minor, 0))
                add("<", _v(major, minor + 1, 0))
            return comparators, pre_triples
        # 缺省段先补 .0：~1 == ~1.0.0，只允许 1.0.x
        mmajor, mminor, mpatch = major, minor if minor is not None else 0, patch if patch is not None else 0
        lower = _v(mmajor, mminor, mpatch, prerelease)
        add(">=", lower)
        if prerelease is not None:
            pre_triples.add((mmajor, mminor, mpatch))
        add("<", _v(mmajor, mminor + 1, 0))
        return comparators, pre_triples

    # >= <= > <（通配操作数：取该范围之外的第一档）
    if wild:
        if minor is None:
            start, beyond = _v(major, 0, 0), _v(major + 1, 0, 0)
        else:
            start, beyond = _v(major, minor, 0), _v(major, minor + 1, 0)
        if op == ">=":
            add(">=", start)
        elif op == ">":
            add(">=", beyond)
        elif op == "<=":
            add("<", beyond)
        else:  # "<"
            add("<", start)
        return comparators, pre_triples

    version = _v(major, minor if minor is not None else 0, patch if patch is not None else 0, prerelease)
    add(op, version)
    if prerelease is not None:
        pre_triples.add((version.major, version.minor, version.patch))
    return comparators, pre_triples


def _parse_branch(text):
    """解析一个 AND 分支，返回合并后的比较子与放行三元组。"""
    comparators = []
    pre_triples = set()
    for token in text.split():
        token_comparators, token_pres = _expand(token)
        comparators.extend(token_comparators)
        pre_triples |= token_pres
    return comparators, pre_triples


def parse_range(text):
    """解析区间文本，返回 :class:`Range`；非法写法抛 ``ValueError``。"""
    if isinstance(text, Range):
        return text
    if not isinstance(text, str):
        raise ValueError(f"区间必须是字符串: {text!r}")

    branches = []
    for part in re.split(r"\s*\|\|\s*", text.strip()):
        if part == "":
            # 空分支（等价于 "*"）：恒真
            branches.append(([], set()))
        else:
            comparators, pre_triples = _parse_branch(part)
            branches.append((comparators, set(pre_triples)))
    return Range(text, branches)


def _cmp(version, other):
    if version < other:
        return -1
    if version > other:
        return 1
    return 0


_OPS = {
    "=": lambda c: c == 0,
    "!=": lambda c: c != 0,
    ">=": lambda c: c >= 0,
    "<=": lambda c: c <= 0,
    ">": lambda c: c > 0,
    "<": lambda c: c < 0,
}


def _branch_matches(version, branch):
    comparators, pre_triples = branch
    if version.prerelease is not None:
        triple = (version.major, version.minor, version.patch)
        if triple not in pre_triples:
            return False
    for op, other in comparators:
        if not _OPS[op](_cmp(version, other)):
            return False
    return True


def match(version, range_text):
    """版本是否满足区间。版本可传字符串或 Version，区间可传字符串或 Range。"""
    parsed = version if isinstance(version, Version) else parse_version(version)
    version_range = parse_range(range_text)
    return any(_branch_matches(parsed, branch) for branch in version_range._branches)


def best(versions, range_text):
    """候选中满足区间的最高优先级版本，没有则返回 None。"""
    version_range = parse_range(range_text)
    satisfied = [
        item if isinstance(item, Version) else parse_version(item)
        for item in versions
        if match(item, version_range)
    ]
    if not satisfied:
        return None
    return max(satisfied)
