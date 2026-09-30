"""subfam.stats: 连续子段统计的朴素实现（改造前基线）。

围绕着整数序列做五件最基础的事，全部靠枚举每一段、再对每一段从头扫描：

  - best_sum       每段各从头累加求和，取和最大的那一段，并列时取最短再取左端最小；
  - bounded_sum    枚举每一段，逐段判断长度是否不超过上界，取其中和最大者；
  - at_most_sum    枚举每一段，逐段判断和是否不超过上界，取满足条件的最大和；
  - range_extremes 枚举每一段，逐段重新扫描出每段内的最大最小，与全序列结果比对；
  - best_product   枚举每一段，逐段重新累乘，区分含零与非零两种情形。

这些做法直观可靠，结果一眼能看穿；段数一多就是立方量级，序列稍长便退化到跑不
完。本文件是改造前的基线，朴素路径在改造之后不得删除，新实现必须与它对同一批数据
给出的事实逐项对齐。每条朴素方法都用一个不可变的返回值对象汇报结果，并顺带记下
本次调用扫描过的元素总次数，规模一眼可见。

异常统一继承 StatsErro 基类：SeqErro / ParamErro。
"""


class StatsErro(Exception):
    """连续子段统计工具包所有异常的基类，非法输入一律快速失败。"""


class SeqErro(StatsErro):
    """序列非法：为空、元素不是整数、不是可迭代对象。"""


class ParamErro(StatsErro):
    """参数非法：上界不是整数、闭区间左右不满足先后关系。"""


class SumReport:
    """一次求和类统计的结果：最优值、该段的左右下标与本次扫描的元素总次数。"""

    __slots__ = ("value", "left", "right", "scan")

    def __init__(self, value, left, right, scan):
        self.value = value
        self.left = left
        self.right = right
        self.scan = scan

    def __eq__(self, other):
        if not isinstance(other, SumReport):
            return NotImplemented
        return (self.value, self.left, self.right) == (other.value, other.left, other.right)

    def __repr__(self):
        return "SumReport(value=%r, left=%r, right=%r, scan=%r)" % (
            self.value, self.left, self.right, self.scan)


class RangeReport:
    """一次区间极值统计的结果：全序列最小值、最大值与本次扫描的元素总次数。"""

    __slots__ = ("min_value", "max_value", "scan")

    def __init__(self, min_value, max_value, scan):
        self.min_value = min_value
        self.max_value = max_value
        self.scan = scan

    def __eq__(self, other):
        if not isinstance(other, RangeReport):
            return NotImplemented
        return (self.min_value, self.max_value) == (other.min_value, other.max_value)

    def __repr__(self):
        return "RangeReport(min_value=%r, max_value=%r, scan=%r)" % (
            self.min_value, self.max_value, self.scan)


class ProductReport:
    """一次求积统计的结果：最优积、是否合零、该段的左右下标与本次累乘次数。"""

    __slots__ = ("value", "has_zero", "left", "right", "scan")

    def __init__(self, value, has_zero, left, right, scan):
        self.value = value
        self.has_zero = has_zero
        self.left = left
        self.right = right
        self.scan = scan

    def __eq__(self, other):
        if not isinstance(other, ProductReport):
            return NotImplemented
        return ((self.value, self.has_zero, self.left, self.right)
                == (other.value, other.has_zero, other.left, other.right))

    def __repr__(self):
        return "ProductReport(value=%r, has_zero=%r, left=%r, right=%r, scan=%r)" % (
            self.value, self.has_zero, self.left, self.right, self.scan)


def _as_int(v, where):
    """把入参规整成 int，非法即抛 SeqErro。"""
    if isinstance(v, bool) or not isinstance(v, int):
        raise SeqErro("%s: 元素必须是整数，收到 %r" % (where, v))
    return int(v)


def _normalize(seq):
    """把入参规整成整数列表，非法即抛 SeqErro。"""
    try:
        items = list(seq)
    except TypeError:
        raise SeqErro("序列必须是可迭代对象，收到 %r" % (seq,))
    return [_as_int(v, "序列") for v in items]


def _check_bound(bound):
    """上界必须是整数且不小于零，否则抛 ParamErro。"""
    if isinstance(bound, bool) or not isinstance(bound, int):
        raise ParamErro("上界必须是整数，收到 %r" % (bound,))
    if bound < 0:
        raise ParamErro("上界不得为负，收到 %r" % (bound,))


def _check_pair(lo, hi):
    """闭区间两端必须是整数且左不大于右，否则抛 ParamErro。"""
    _check_bound(lo)
    _check_bound(hi)
    if lo > hi:
        raise ParamErro("区间左端不得大于右端，收到 %r 与 %r" % (lo, hi))


def _span_sum(vals, i, j):
    """从头累加闭区间 vals[i..j] 的和，返回和与本次累加次数。"""
    total = 0
    for t in range(i, j + 1):
        total += vals[t]
    return total, (j - i + 1)


class SubarrayStats:
    """连续子段统计朴素工具集（改造前基线）。

    每次调用都从零重新枚举全部子段，实例本身不保存任何跨调用的派生状态；同一批输入
    连续调用两次，结果与扫描次数都应逐位一致。
    """

    def __init__(self):
        # 仅供上层参考的最近一次调用扫描次数，进入调用前归零后重新累加。
        self.last_scan = 0

    # ----------------------------------------------------------------
    # 最大子段和：枚举全部子段，每段从头累加
    # ----------------------------------------------------------------
    def best_sum(self, seq):
        """最大子段和，返回 SumReport。

        空序列的最优值取零，此时左右下标都为负一，表示空段。并列时取长度最小者，长度
        仍相同再取左端点最小者。非法输入抛 SeqErro。
        """
        vals = _normalize(seq)
        n = len(vals)
        if n == 0:
            self.last_scan = 0
            return SumReport(0, -1, -1, 0)
        best = None
        best_l = best_r = 0
        scan = 0
        for i in range(n):
            for j in range(i, n):
                total, steps = _span_sum(vals, i, j)
                scan += steps
                len_new = j - i + 1
                if best is None:
                    take = True
                elif total > best:
                    take = True
                elif total == best and len_new < (best_r - best_l + 1):
                    take = True
                else:
                    take = False
                if take:
                    best = total
                    best_l = i
                    best_r = j
        self.last_scan = scan
        return SumReport(best, best_l, best_r, scan)

    # ----------------------------------------------------------------
    # 上界内最大子段和：枚举全部子段，逐段判断长度
    # ----------------------------------------------------------------
    def bounded_sum(self, seq, bound):
        """长度不超过 bound 的子段中最大的和，返回 SumReport。

        bound 为零时只允许空段，最优值取零、左右下标都为负一。并列时取长度最小者，
        再取左端点最小者。上界非法抛 ParamErro，序列非法抛 SeqErro。
        """
        _check_bound(bound)
        vals = _normalize(seq)
        n = len(vals)
        if n == 0 or bound == 0:
            self.last_scan = 0
            return SumReport(0, -1, -1, 0)
        best = None
        best_l = best_r = 0
        scan = 0
        for i in range(n):
            for j in range(i, n):
                if j - i + 1 > bound:
                    break
                total, steps = _span_sum(vals, i, j)
                scan += steps
                len_new = j - i + 1
                if best is None or total > best or (
                        total == best and len_new < (best_r - best_l + 1)):
                    best = total
                    best_l = i
                    best_r = j
        self.last_scan = scan
        return SumReport(best, best_l, best_r, scan)

    # ----------------------------------------------------------------
    # 和最接近上界：枚举全部子段，逐段判断和
    # ----------------------------------------------------------------
    def at_most_sum(self, seq, bound):
        """和不超过 bound 的子段中最大的和，返回 SumReport。

        没有任何非空子段满足条件时最优值取零、左右下标都为负一。并列时取长度最小者，
        再取左端点最小者。上界非法抛 ParamErro，序列非法抛 SeqErro。
        """
        _check_bound(bound)
        vals = _normalize(seq)
        n = len(vals)
        best = None
        best_l = best_r = 0
        scan = 0
        for i in range(n):
            total = 0
            for j in range(i, n):
                total += vals[j]
                scan += 1
                if total > bound:
                    break
                len_new = j - i + 1
                if best is None or total > best or (
                        total == best and len_new < (best_r - best_l + 1)):
                    best = total
                    best_l = i
                    best_r = j
        self.last_scan = scan
        if best is None:
            return SumReport(0, -1, -1, scan)
        return SumReport(best, best_l, best_r, scan)

    # ----------------------------------------------------------------
    # 极值对照：枚举全部子段，逐段重新扫描出段内极值
    # ----------------------------------------------------------------
    def range_extremes(self, seq):
        """返回 RangeReport，汇总全序列的最小值与最大值，并顺带做逐段极值的枚举。

        逐段枚举只是为与全序列扫描的结果相互印证，段内极值都落在全序列极值区间内；
        非空序列必满足这一关系，空序列在入口直接以 SeqErro 拒绝。规模一长就退化成
        立方量级。非法输入抛 SeqErro。
        """
        vals = _normalize(seq)
        if not vals:
            raise SeqErro("极值对照需要非空序列")
        scan = 0
        lo = vals[0]
        hi = vals[0]
        for v in vals:
            scan += 1
            if v < lo:
                lo = v
            if v > hi:
                hi = v
        n = len(vals)
        for i in range(n):
            for j in range(i, n):
                seg_lo = vals[i]
                seg_hi = vals[i]
                for t in range(i, j + 1):
                    scan += 1
                    if vals[t] < seg_lo:
                        seg_lo = vals[t]
                    if vals[t] > seg_hi:
                        seg_hi = vals[t]
                if seg_lo < lo or seg_hi > hi:
                    raise StatsErro("段内极值越出全序列极值，实现有误")
        self.last_scan = scan
        return RangeReport(lo, hi, scan)

    # ----------------------------------------------------------------
    # 最大子段积：枚举全部子段，逐段重新累乘
    # ----------------------------------------------------------------
    def best_product(self, seq):
        """最大子段积，返回 ProductReport。

        空序列的最优积取零、是否合零为真，左右下标都为负一。并列时取乘积最大者，乘积
        相同再取长度最小者，仍相同取左端点最小者；是否合零取到最优段是否含零元。
        非法输入抛 SeqErro。
        """
        vals = _normalize(seq)
        n = len(vals)
        if n == 0:
            self.last_scan = 0
            return ProductReport(0, True, -1, -1, 0)
        best = None
        best_zero = False
        best_l = best_r = 0
        scan = 0
        for i in range(n):
            for j in range(i, n):
                prod = 1
                zero = False
                for t in range(i, j + 1):
                    scan += 1
                    v = vals[t]
                    if v == 0:
                        zero = True
                    prod *= v
                len_new = j - i + 1
                if best is None or prod > best or (
                        prod == best and len_new < (best_r - best_l + 1)):
                    best = prod
                    best_zero = zero
                    best_l = i
                    best_r = j
        self.last_scan = scan
        return ProductReport(best, best_zero, best_l, best_r, scan)
