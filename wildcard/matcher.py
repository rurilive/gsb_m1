"""朴素通配符匹配: 用最直白的递归回溯判定完全匹配。

这是改造前的基线实现。匹配只看两种通配符: 问号匹配恰好一个任意字符,
星号匹配任意长度 (零个或多个) 的字符序列。判定完全匹配时, 遇到星号就
把它展开成零个、一个、两个一直到多个字符逐个递归尝试, 不做任何缓存,
也不做任何剪枝。模式里星号一多, 同一个子问题会被反复展开, 最坏情况下的
展开层数随星号个数指数级增长, 文本一长就慢得没法用。

匹配长度口径写死: 匹配成功时, 每个星号 (相邻星号先合并成一个) 实际吃掉的
文本字符个数, 按星号在模式中从左到右的先后顺序给出; 并列 (同一个星号能
吃掉不同长度却都能整体匹配) 时, 前面的星号尽可能少吃, 即取能整体匹配的
最小长度, 剩余交给后面的星号与固定字符去消化, 这样同一对文本与模式重复
跑多次给出的长度序列永远相同。
"""


class Erro(Exception):
    """本包所有自定义异常的公共基类, 便于调用方统一捕获。"""


class TypeMismatchError(Erro):
    """文本或模式不是字符串时抛出。"""


class PatternError(Erro):
    """模式中含有不受支持的通配符 (既非问号也非星号) 时抛出。"""


class NoMatchError(Erro):
    """要求给出星号匹配长度, 但文本与模式根本无法整体匹配时抛出。"""


def _check(text, pattern):
    """校验文本与模式都是字符串, 并校验模式的字符集合法。"""
    if not isinstance(text, str) or not isinstance(pattern, str):
        raise TypeMismatchError("text and pattern must be str")
    for ch in pattern:
        if ch not in ("?", "*") and not ("a" <= ch <= "z"):
            raise PatternError("unsupported pattern char: " + repr(ch))
    return text, pattern


def _merge(pattern):
    """把相邻的星号合并成一个, 返回合并后的模式。"""
    out = []
    for ch in pattern:
        if ch == "*" and out and out[-1] == "*":
            continue
        out.append(ch)
    return "".join(out)


def _segments(merged):
    """返回把已合并的模式按星号切开的非空固定段列表。"""
    return [seg for seg in merged.split("*") if seg != ""]


def _rec(text, pattern):
    """最直白的递归回溯判定完全匹配, 不做缓存。"""
    if pattern == "":
        return text == ""
    head = pattern[0]
    rest = pattern[1:]
    if head == "?":
        return text != "" and _rec(text[1:], rest)
    if head == "*":
        if _rec(text, rest):
            return True
        return text != "" and _rec(text[1:], pattern)
    return text != "" and text[0] == head and _rec(text[1:], rest)


def _seg_match(seg, text, start):
    """固定段 (只含字面字符与问号) 能否在 text 的 start 处整段对上。"""
    if start + len(seg) > len(text):
        return False
    for i, ch in enumerate(seg):
        if ch != "?" and ch != text[start + i]:
            return False
    return True


def _place(text, segs, idx, start, free_end):
    """从 idx 起给每个固定段取最早可行起点; 不可行返回 None。

    free_end 为真表示最后一段之后还有星号兜底, 不要求与文本末尾对齐; 否则
    最后一段必须正好在文本末尾收尾。每一段都取满足整体可行性的最早起点,
    于是前面的星号总是尽可能少吃, 对应写死的最小长度口径。
    """
    if idx == len(segs):
        return [] if (free_end or start == len(text)) else None
    seg = segs[idx]
    is_last = idx == len(segs) - 1
    s = start
    while s + len(seg) <= len(text):
        if _seg_match(seg, text, s):
            if is_last:
                if free_end or s + len(seg) == len(text):
                    return [s]
            else:
                tail = _place(text, segs, idx + 1, s + len(seg), free_end)
                if tail is not None:
                    return [s] + tail
        s += 1
    return None


def _star_lengths(text, merged):
    """给出每个星号吃掉的字符数; 整体不匹配时抛 NoMatchError。"""
    if merged.count("*") == 0:
        if _rec(text, merged):
            return ()
        raise NoMatchError("pattern does not match text")

    segs = _segments(merged)
    starts_with_star = merged[0] == "*"
    ends_with_star = merged[-1] == "*"

    if not segs:
        # 整条模式全是星号, 合并后只剩一个。
        return (len(text),)

    if starts_with_star:
        starts = _place(text, segs, 0, 0, ends_with_star)
    else:
        if not _seg_match(segs[0], text, 0):
            raise NoMatchError("pattern does not match text")
        tail = _place(text, segs, 1, len(segs[0]), ends_with_star)
        starts = None if tail is None else [0] + tail
    if starts is None:
        raise NoMatchError("pattern does not match text")

    lengths = []
    if starts_with_star:
        lengths.append(starts[0])
    for k in range(1, len(starts)):
        lengths.append(starts[k] - (starts[k - 1] + len(segs[k - 1])))
    if ends_with_star:
        lengths.append(len(text) - (starts[-1] + len(segs[-1])))
    return tuple(lengths)


class NaiveWildcard:
    """一个文本与一个模式, 用递归回溯判定是否完全匹配, 并给出星号吃掉的长度。

    整个类不保存任何可变状态: 文本与模式在构造时固定, 之后每次调用都从头
    计算, 同一对输入重复跑多次给出的结论与长度序列完全一致。
    """

    def __init__(self, text, pattern):
        self._text, self._pattern = _check(text, pattern)

    @property
    def text(self):
        """返回构造时固定的文本。"""
        return self._text

    @property
    def pattern(self):
        """返回构造时固定的模式。"""
        return self._pattern

    def matches(self):
        """完全匹配返回真, 否则返回假; 用递归回溯实现, 不做缓存。"""
        return _rec(self._text, self._pattern)

    def star_count(self):
        """返回合并相邻星号之后, 模式里星号的个数。"""
        return _merge(self._pattern).count("*")

    def star_lengths(self):
        """返回每个星号吃掉的字符数 (元组, 按星号从左到右); 不匹配抛 NoMatchError。"""
        return _star_lengths(self._text, _merge(self._pattern))


def star_lengths(pattern, text):
    """模块级独立做法: 给定模式与文本, 返回星号匹配长度元组; 不匹配抛 NoMatchError。

    参数顺序与类相反 (先模式后文本), 方便上层按模式批量套用同一个文本。
    """
    _check(text, pattern)
    return _star_lengths(text, _merge(pattern))
