"""slidewin.window: 数组与字符串窗口统计的朴素实现（改造前基线）。

一手整数数组、一手字符文本，围绕窗口做四件事，全部靠枚举左右端点、对每个候选窗口
从头重新判断并重新扫描：

  - sum_bounds    两次枚举全部连续子数组，对每段从头重新求和，分别得到和不小于目标的
                  最短子数组长度、和不大于目标的最长子数组长度；
  - longest_distinct    枚举全部子串，逐个子串从头重新统计不同字符数并判断；
  - distinct_count    对恰好含某数量不同字符的计数，走至多相减的口径，至多本身也是
                  逐个子串从头重新统计；
  - cover_window    枚举全部子串，逐个检查是否覆盖全部目标字符并取最短。

这些做法直观可靠，结果一眼看穿；窗口一多就是平方量级，每个窗口再从头重扫一遍就退化
成立方量级，文本稍长便跑不完。本文件是改造前的基线，朴素路径在改造之后不得删除，新
实现必须与它对同一批数据给出的事实逐项对齐。每条朴素方法都用不可变的返回值对象汇报
结果，并顺带记下本次调用扫描过的元素总次数，规模一眼可见。

异常统一继承 SlideErro 基类：SeqErro / ParamErro。
"""


class SlideErro(Exception):
    """窗口统计工具包所有异常的基类，非法输入一律快速失败。"""


class SeqErro(SlideErro):
    """序列非法：为空、元素不是整数、不是可迭代对象；文本非法同理。"""


class ParamErro(SlideErro):
    """参数非法：目标不是整数、不同字符上界不是整数、目标字符集为空。"""


class SumReport:
    """一次求和类窗口统计的结果：最短长度与最长长度，以及本次扫描的元素总次数。"""

    __slots__ = ("short_len", "long_len", "scan")

    def __init__(self, short_len, long_len, scan):
        self.short_len = short_len
        self.long_len = long_len
        self.scan = scan

    def __eq__(self, other):
        if not isinstance(other, SumReport):
            return NotImplemented
        return (self.short_len, self.long_len) == (other.short_len, other.long_len)

    def __repr__(self):
        return "SumReport(short_len=%r, long_len=%r, scan=%r)" % (
            self.short_len, self.long_len, self.scan)


class DistinctReport:
    """一次不同字符统计的结果：最优长度、出现位置左端与本次扫描的元素总次数。"""

    __slots__ = ("length", "left", "scan")

    def __init__(self, length, left, scan):
        self.length = length
        self.left = left
        self.scan = scan

    def __eq__(self, other):
        if not isinstance(other, DistinctReport):
            return NotImplemented
        return (self.length, self.left) == (other.length, other.left)

    def __repr__(self):
        return "DistinctReport(length=%r, left=%r, scan=%r)" % (
            self.length, self.left, self.scan)


def _as_int(v, where):
    """把入参规整成 int，非法即抛 SeqErro。"""
    if isinstance(v, bool) or not isinstance(v, int):
        raise SeqErro("%s: 元素必须是整数，收到 %r" % (where, v))
    return int(v)


def _to_list(seq):
    """把入参规整成整数列表，非法即抛 SeqErro。"""
    try:
        items = list(seq)
    except TypeError:
        raise SeqErro("序列必须是可迭代对象，收到 %r" % (seq,))
    return [_as_int(v, "序列") for v in items]


def _to_text(text):
    """把入参规整成字符列表，非法即抛 SeqErro。"""
    if not isinstance(text, str):
        raise SeqErro("文本必须是字符串，收到 %r" % (text,))
    return list(text)


def _check_int(value, where):
    """目标必须是整数，否则抛 ParamErro。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ParamErro("%s必须是整数，收到 %r" % (where, value))


def _distinct(text, i, j):
    """从头重新统计闭区间 text[i..j] 里的不同字符数，返回计数与本次扫描次数。"""
    seen = set()
    for t in range(i, j + 1):
        seen.add(text[t])
    return len(seen), (j - i + 1)


def _covers(text, i, j, target):
    """从头重新检查闭区间是否覆盖全部目标字符，返回是否覆盖与本次扫描次数。"""
    seen = set()
    for t in range(i, j + 1):
        seen.add(text[t])
    return target <= seen, (j - i + 1)


class WindowStats:
    """窗口统计朴素工具集（改造前基线）。

    每次调用都从零重新枚举全部窗口，实例本身不保存任何跨调用的派生状态；同一批输入
    连续调用两次，结果与扫描次数都应逐位一致。
    """

    def __init__(self):
        # 仅供上层参考的最近一次调用扫描次数，进入调用前归零后重新累加。
        self.last_scan = 0

    # ----------------------------------------------------------------
    # 和最短与和最长：两次枚举全部子数组，每段从头重新求和
    # ----------------------------------------------------------------
    def sum_bounds(self, seq, target):
        """返回 SumReport，含和不小于目标的最短长度与和不大于目标的最长长度。

        没有任何子数组满足条件时对应长度取零。目标非法抛 ParamErro，序列非法抛
        SeqErro。
        """
        _check_int(target, "目标和")
        vals = _to_list(seq)
        n = len(vals)
        short_len = 0
        long_len = 0
        scan = 0
        for i in range(n):
            for j in range(i, n):
                total, steps = 0, 0
                for t in range(i, j + 1):
                    total += vals[t]
                    steps += 1
                scan += steps
                span = j - i + 1
                if total >= target:
                    if short_len == 0 or span < short_len:
                        short_len = span
                if total <= target:
                    if span > long_len:
                        long_len = span
        self.last_scan = scan
        return SumReport(short_len, long_len, scan)

    # ----------------------------------------------------------------
    # 至多含若干不同字符的最长子串：枚举全部子串，逐个从头重新统计
    # ----------------------------------------------------------------
    def longest_distinct(self, text, cap):
        """返回 DistinctReport，给至多含 cap 个不同字符的最长子串的长度与左端。

        没有任何满足条件的非空子串时长度取零、左端为负一。cap 非法抛 ParamErro，
        文本非法抛 SeqErro。
        """
        _check_int(cap, "不同字符上界")
        if cap < 0:
            raise ParamErro("不同字符上界不得为负，收到 %r" % (cap,))
        chars = _to_text(text)
        n = len(chars)
        best = 0
        best_l = -1
        scan = 0
        for i in range(n):
            for j in range(i, n):
                cnt, steps = _distinct(chars, i, j)
                scan += steps
                if cnt <= cap:
                    span = j - i + 1
                    if span > best:
                        best = span
                        best_l = i
        self.last_scan = scan
        return DistinctReport(best, best_l, scan)

    # ----------------------------------------------------------------
    # 恰好含若干不同字符的子串个数：至多相减的口径
    # ----------------------------------------------------------------
    def distinct_count(self, text, cap):
        """返回至多含 cap 个不同字符的子串数减去至多含 cap 减一个不同字符的子串数。

        cap 为零时就退化成全由同一字符构成的子串的个数。cap 非法抛 ParamErro，文本
        非法抛 SeqErro。
        """
        _check_int(cap, "不同字符上界")
        if cap < 0:
            raise ParamErro("不同字符上界不得为负，收到 %r" % (cap,))
        chars = _to_text(text)
        n = len(chars)
        scan = 0

        def at_most(k):
            """统计至多含 k 个不同字符的子串个数，逐个子串从头重新统计。

            非空子串至少含一个不同字符，故上界为零或更小时计数为零。
            """
            nonlocal scan
            if k <= 0:
                return 0
            total = 0
            for i in range(n):
                for j in range(i, n):
                    cnt, steps = _distinct(chars, i, j)
                    scan += steps
                    if cnt <= k:
                        total += 1
            return total

        result = at_most(cap) - at_most(cap - 1)
        self.last_scan = scan
        return result

    # ----------------------------------------------------------------
    # 覆盖全部目标字符的最短窗口：枚举全部子串，逐个从头检查覆盖
    # ----------------------------------------------------------------
    def cover_window(self, text, target):
        """返回最短覆盖窗口的左右端点与长度三元组，无解时返回 (-1, -1, 0)。

        target 是待覆盖的目标字符集合，为空时抛 ParamErro。文本非法抛 SeqErro。
        """
        chars = _to_text(text)
        if isinstance(target, str):
            need = set(target)
        else:
            try:
                need = set(target)
            except TypeError:
                raise ParamErro("目标字符集必须是可迭代对象，收到 %r" % (target,))
        if not need:
            raise ParamErro("目标字符集不得为空")
        n = len(chars)
        best_len = 0
        best_l = -1
        best_r = -1
        scan = 0
        for i in range(n):
            for j in range(i, n):
                ok, steps = _covers(chars, i, j, need)
                scan += steps
                if ok:
                    span = j - i + 1
                    if best_len == 0 or span < best_len:
                        best_len = span
                        best_l = i
                        best_r = j
        self.last_scan = scan
        return (best_l, best_r, best_len)
