"""semver 2.0.0 的解析与优先级比较。"""

import functools
import re

_SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)


def _prerelease_key(prerelease):
    """预发布串转成可比较的键；正式版排在整个元组空间的最后。"""
    if prerelease is None:
        return (1,)
    out = []
    for part in prerelease.split("."):
        if part.isascii() and part.isdigit():
            # 数字标识符的优先级低于字母数字标识符
            out.append((0, int(part), ""))
        else:
            out.append((1, 0, part))
    return (0,) + tuple(out)


@functools.total_ordering
class Version:
    """一个 semver 版本：major.minor.patch[-prerelease][+build]。

    build 元数据只在 str() 里保留，不参与优先级比较。
    """

    def __init__(self, major, minor, patch, prerelease=None, build=None):
        for name, value in (("major", major), ("minor", minor), ("patch", patch)):
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} 必须是非负整数: {value!r}")
        self.major = major
        self.minor = minor
        self.patch = patch
        self.prerelease = prerelease or None
        self.build = build or None

    def _key(self):
        return (self.major, self.minor, self.patch, _prerelease_key(self.prerelease))

    def __repr__(self):
        return f"Version({str(self)!r})"

    def __str__(self):
        s = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            s += "-" + self.prerelease
        if self.build:
            s += "+" + self.build
        return s

    def __eq__(self, other):
        if not isinstance(other, Version):
            return NotImplemented
        return self._key() == other._key()

    def __hash__(self):
        return hash(self._key())

    def __lt__(self, other):
        if not isinstance(other, Version):
            other = parse_version(other)
        return self._key() < other._key()


def parse_version(text):
    """解析 semver 字符串，非法输入抛 ValueError。

    严格模式：不接受 v 前缀、首尾空白、多段、前导零。
    """
    if isinstance(text, Version):
        return text
    if not isinstance(text, str):
        raise ValueError(f"版本必须是字符串: {text!r}")
    m = _SEMVER_RE.match(text)
    if not m:
        raise ValueError(f"不是合法的 semver: {text!r}")
    return Version(
        int(m.group(1)),
        int(m.group(2)),
        int(m.group(3)),
        prerelease=m.group(4),
        build=m.group(5),
    )


def compare(a, b):
    """比较两个版本的优先级，返回 -1/0/1。

    参数可以是 Version 或 semver 字符串。build 元数据不参与比较。
    """
    ka = (a if isinstance(a, Version) else parse_version(a))._key()
    kb = (b if isinstance(b, Version) else parse_version(b))._key()
    if ka < kb:
        return -1
    if ka > kb:
        return 1
    return 0
