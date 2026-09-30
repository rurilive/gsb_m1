"""minrot 的朴素循环字符串工具（改造前的现状）。

现在只有一条路：最小字典序循环旋转枚举全部 n 个起点，每个起点取出
长度 n 的子串，再把各子串两两比较；循环同构判定拿一个串的全部旋转
逐个去和另一个串比对；最大字典序旋转与最短位移同样枚举。结果都对，
但规模一大就成平方以上量级。线性做法见任务描述。
"""


class Erro(Exception):
    """本模块所有对外异常的公共基类。"""


class RotError(Erro):
    """字符串或旋转参数的非法输入。"""


def _check_text(text, name="text"):
    """字符串必须非空，允许为空串的场合由调用方另行放行。"""
    if not isinstance(text, str):
        raise RotError("%s must be a str" % name)
    return text


def _check_nonempty(text, name="text"):
    """字符串必须是非空字符串，用于最小与最大旋转等入口。"""
    if not isinstance(text, str):
        raise RotError("%s must be a str" % name)
    if text == "":
        raise RotError("%s must not be empty" % name)
    return text


def _rotations(text):
    """把字符串的全部循环旋转按起点升序列出，每个都是长度 n 的新串。"""
    n = len(text)
    if n == 0:
        return [""]
    return [text[i:] + text[:i] for i in range(n)]


def min_rotation_index(text):
    """最小字典序循环旋转的起点下标，枚举全部起点逐个比较。

    并列时取最小的起点下标。空串按起点零处理。
    """
    _check_text(text)
    n = len(text)
    if n == 0:
        return 0
    best = 0
    for i in range(1, n):
        if text[i:] + text[:i] < text[best:] + text[:best]:
            best = i
    return best


def min_rotation(text):
    """最小字典序循环旋转串，枚举全部起点后逐串比较。"""
    _check_nonempty(text)
    return text[min_rotation_index(text):] + text[:min_rotation_index(text)]


def max_rotation_index(text):
    """最大字典序循环旋转的起点下标，枚举全部起点逐个比较。

    并列时取最小的起点下标。空串按起点零处理。
    """
    _check_text(text)
    n = len(text)
    if n == 0:
        return 0
    best = 0
    for i in range(1, n):
        if text[i:] + text[:i] > text[best:] + text[:best]:
            best = i
    return best


def max_rotation(text):
    """最大字典序循环旋转串，枚举全部起点后逐串比较。"""
    _check_nonempty(text)
    return text[max_rotation_index(text):] + text[:max_rotation_index(text)]


def is_rotation(a, b):
    """两个串是否循环同构：长度相等且一个的全部旋转中出现另一个。"""
    _check_text(a, "a")
    _check_text(b, "b")
    if len(a) != len(b):
        return False
    if a == "":
        return True
    return b in _rotations(a)


def min_shift(a, b):
    """由 a 循环左移多少位得到 b，不可同构时返回负一。

    枚举 a 的全部旋转，取首次与 b 相等的位移，即并列时最小的位移。
    """
    _check_text(a, "a")
    _check_text(b, "b")
    if len(a) != len(b):
        return -1
    if a == "":
        return 0
    n = len(a)
    for i in range(n):
        if a[i:] + a[:i] == b:
            return i
    return -1


class RotTools:
    """绑定一个字符串的循环旋转工具，只有逐起点枚举这一条路。

    每个方法都按最直白的循环与切片完成，并把字符比较的次数累计进
    计数器，供与线性做法对照规模。字符串在构造时校验并固定。
    """

    def __init__(self, text):
        self._text = _check_text(text)
        self._compare_count = 0

    def text(self):
        """返回绑定的字符串。"""
        return self._text

    def reset_compare_count(self):
        """把字符比较计数清零。"""
        self._compare_count = 0

    def compare_count(self):
        """自上次清零以来累计比较了多少个字符位置。"""
        return self._compare_count

    def _cmp(self, x, y):
        """逐字符比较两个等长串，返回负数、零或正数，并累计比较次数。"""
        limit = len(x) if len(x) < len(y) else len(y)
        for k in range(limit):
            self._compare_count += 1
            if x[k] != y[k]:
                return -1 if x[k] < y[k] else 1
        self._compare_count += 1
        if len(x) == len(y):
            return 0
        return -1 if len(x) < len(y) else 1

    def min_rotation_index(self):
        """最小字典序循环旋转的起点下标，逐起点枚举比较并计数。"""
        text = self._text
        n = len(text)
        if n == 0:
            return 0
        best = 0
        best_rot = text
        for i in range(1, n):
            rot = text[i:] + text[:i]
            if self._cmp(rot, best_rot) < 0:
                best = i
                best_rot = rot
        return best

    def min_rotation(self):
        """最小字典序循环旋转串，逐起点枚举比较并计数。"""
        _check_nonempty(self._text)
        return self._rot(self.min_rotation_index())

    def max_rotation_index(self):
        """最大字典序循环旋转的起点下标，逐起点枚举比较并计数。"""
        text = self._text
        n = len(text)
        if n == 0:
            return 0
        best = 0
        best_rot = text
        for i in range(1, n):
            rot = text[i:] + text[:i]
            if self._cmp(rot, best_rot) > 0:
                best = i
                best_rot = rot
        return best

    def max_rotation(self):
        """最大字典序循环旋转串，逐起点枚举比较并计数。"""
        _check_nonempty(self._text)
        return self._rot(self.max_rotation_index())

    def _rot(self, i):
        """绑定串从起点 i 循环左移得到的旋转串。"""
        return self._text[i:] + self._text[:i]

    def is_rotation(self, other):
        """绑定串与另一个串是否循环同构，逐旋转比对并计数。"""
        _check_text(other, "other")
        text = self._text
        if len(text) != len(other):
            return False
        if text == "":
            return True
        n = len(text)
        for i in range(n):
            if self._cmp(text[i:] + text[:i], other) == 0:
                return True
        return False

    def min_shift(self, other):
        """由绑定串循环左移得到另一个串的最小位移，不可同构返回负一。"""
        _check_text(other, "other")
        text = self._text
        if len(text) != len(other):
            return -1
        if text == "":
            return 0
        n = len(text)
        for i in range(n):
            if self._cmp(text[i:] + text[:i], other) == 0:
                return i
        return -1
