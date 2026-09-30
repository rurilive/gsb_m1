"""digitcount.count: 区间按位计数工具（当前为改造前基线）。

本模块提供 IntervalCounter，用来统计一个闭区间内满足数字条件的整数个数。
当前实现全部是朴素逐数枚举：从区间下界一路数到上界，对每一个整数取出它的
各位数字再逐条判定，四个计数能力共用同一个判定核心。

  - count_without_digit：区间内十进制表示不含某个数字的数的个数；
  - count_digit_sum：区间内各位数字之和恰为某个值的数的个数；
  - count_strict_increasing：区间内相邻两位严格递增的数的个数；
  - count_multiple：区间内十进制数值为某个数之整数倍的数的个数。

四条能力之外还给出一个求具体数的最小值能力：

  - find_minimum：区间内满足条件的最小整数，不存在则返回 None。

另给两条独立的慢速做法用于与新路逐项对照：逐数枚举逐个判定（与主路径口径
一致但独立成路），以及针对具体数查询的独立枚举。区间一大，逐数枚举的次数
就随区间长度线性增长，每个数还要按位数再逐位走一遍；多次查询时差距更明显。

全部只依赖标准库。
"""

# 十进制数字的个数字母表，数组下标即数值。
_DIGIT_CHARS = "0123456789"

# 递归树的最大深度上限，即数字的最大位数，超过即判为规模过大。
MAX_DIGITS = 18

# 缺省进制；本包一律按十进制计数，该常量作为口径标记导出。
DEFAULT_BASE = 10


class Erro(Exception):
    """本包所有异常的根，上层只认这一个。"""


class RangeErro(Erro):
    """区间端点不合法，如下界大于上界或不是整数。"""


class ValueErro(Erro):
    """计数参数不合法，如目标数字、目标和或模数越界。"""


class ParamErro(Erro):
    """查询参数不合法，如条件名不认识或参数个数不对。"""


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


class IntervalCounter:
    """区间按位计数工具（基线朴素版）。

    四条计数能力都作用在一个闭区间 [low, high] 上，下界与上界均必须是不小于
    零的整数且下界不得大于上界。区间端点通过 set_range 设定或直接传给每个
    计数方法；不传时沿用上一次 set_range 设定或方法入参留下的区间。

    设置区间时立即校验端点：下界大于上界、任一端点不是整数、上界的位数超过
    MAX_DIGITS 都要在入口拒绝。每次计数前把上一次记下的逐数判定次数归零重算。
    """

    def __init__(self, low=0, high=0):
        self._low = None
        self._high = None
        self._digits = 1
        self.set_range(low, high)
        self._reset_counts()

    # ---------------------------------------------------------------- 基本

    def set_range(self, low, high):
        """设定当前区间为 [low, high]，立即校验端点。"""
        if not _is_int(low) or not _is_int(high):
            raise RangeErro("区间端点必须是不小于零的整数：%r, %r" % (low, high))
        if low < 0 or high < 0:
            raise RangeErro("区间端点必须是不小于零的整数：%r, %r" % (low, high))
        if low > high:
            raise RangeErro("区间下界不得大于上界：%r > %r" % (low, high))
        if self._num_digits(high) > MAX_DIGITS:
            raise RangeErro("上界位数超过上限 %d：%r" % (MAX_DIGITS, high))
        self._low = low
        self._high = high
        self._digits = self._num_digits(high)
        return self

    def _pick_range(self, low, high):
        if low is None and high is None:
            if self._low is None:
                raise RangeErro("尚未设定区间")
            return self._low, self._high
        if low is None or high is None:
            raise RangeErro("区间端点必须成对给出：%r, %r" % (low, high))
        self.set_range(low, high)
        return self._low, self._high

    def _reset_counts(self):
        self.enumerate_visits = 0
        self.digit_visits = 0
        self.state_visits = 0

    @staticmethod
    def _num_digits(value):
        return len(str(int(value)))

    def _digits_of(self, number):
        """取一个非负整数的各位数字，高位在前。"""
        return [int(ch) for ch in str(int(number))]

    # ------------------------------------------------------- 条件判定核

    def _first_missing_digit(self, digit):
        """返回一个判定函数：数字的十进制表示中不含给定数字则为真。"""
        if not _is_int(digit) or digit < 0 or digit >= 10:
            raise ValueErro("目标数字必须是零到九之间的整数：%r" % (digit,))

        def predicate(number):
            self.digit_visits += 1
            return _DIGIT_CHARS[digit] not in str(int(number))

        return predicate

    def _sum_equals(self, target):
        """返回一个判定函数：数字的各位数字之和恰为给定目标则为真。"""
        if not _is_int(target) or target < 0:
            raise ValueErro("数字和必须是不小于零的整数：%r" % (target,))

        def predicate(number):
            self.digit_visits += len(str(int(number)))
            return sum(self._digits_of(number)) == target

        return predicate

    def _strictly_increasing(self):
        """返回一个判定函数：数字相邻两位从左到右严格递增则为真。"""

        def predicate(number):
            digits = self._digits_of(number)
            self.digit_visits += len(digits)
            return all(digits[i] < digits[i + 1] for i in range(len(digits) - 1))

        return predicate

    def _is_multiple(self, base):
        """返回一个判定函数：数字的十进制数值为给定数之整数倍则为真。"""
        if not _is_int(base) or base < 0:
            raise ValueErro("倍数底数必须是不小于零的整数：%r" % (base,))
        if base == 0:
            raise ValueErro("倍数底数不得为零")

        def predicate(number):
            self.digit_visits += 1
            return int(number) % base == 0

        return predicate

    # -------------------------------------------------------- 朴素计数

    def _enumerate(self, low, high, predicate):
        """从下界逐个数到上界逐个判定，累计满足条件的个数。"""
        total = 0
        for number in range(int(low), int(high) + 1):
            self.enumerate_visits += 1
            if predicate(number):
                total += 1
        return total

    def count_without_digit(self, digit, low=None, high=None):
        """区间内不含给定数字的数的个数（朴素逐数枚举）。"""
        low, high = self._pick_range(low, high)
        self._reset_counts()
        return self._enumerate(low, high, self._first_missing_digit(digit))

    def count_digit_sum(self, target, low=None, high=None):
        """区间内各位数字之和恰为给定值的数的个数（朴素逐数枚举）。"""
        low, high = self._pick_range(low, high)
        self._reset_counts()
        return self._enumerate(low, high, self._sum_equals(target))

    def count_strict_increasing(self, low=None, high=None):
        """区间内相邻两位严格递增的数的个数（朴素逐数枚举）。"""
        low, high = self._pick_range(low, high)
        self._reset_counts()
        return self._enumerate(low, high, self._strictly_increasing())

    def count_multiple(self, base, low=None, high=None):
        """区间内为给定数之整数倍的数的个数（朴素逐数枚举）。"""
        low, high = self._pick_range(low, high)
        self._reset_counts()
        return self._enumerate(low, high, self._is_multiple(base))

    # -------------------------------------------------------- 具体数查询

    def find_minimum(self, condition, arg=None, low=None, high=None):
        """区间内满足条件的最小整数，不存在则返回 None（朴素逐数枚举）。

        condition 取字符串名，arg 为对应参数：without_digit 需要一个数字，
        digit_sum 需要一个目标和，strict_increasing 不需参数，multiple 需要
        一个倍数底数。名字不认识或参数不对一律报 ParamErro。
        """
        low, high = self._pick_range(low, high)
        predicate = self._make_predicate(condition, arg)
        self._reset_counts()
        for number in range(int(low), int(high) + 1):
            self.enumerate_visits += 1
            if predicate(number):
                return number
        return None

    def _make_predicate(self, condition, arg):
        if not isinstance(condition, str):
            raise ParamErro("条件名必须是字符串：%r" % (condition,))
        if condition == "without_digit":
            return self._first_missing_digit(arg)
        if condition == "digit_sum":
            return self._sum_equals(arg)
        if condition == "strict_increasing":
            return self._strictly_increasing()
        if condition == "multiple":
            return self._is_multiple(arg)
        raise ParamErro("不认识的条件名：%r" % (condition,))

    # --------------------------------------------------- 独立慢速做法一

    def independent_enumerate(self, condition, arg=None, low=None, high=None):
        """独立做法一：逐数枚举逐个判定，独立成路再数一遍。

        与主路径口径一致，但不着主路径的计数器，自记独立计数。
        """
        low, high = self._pick_range(low, high)
        self._reset_counts()
        total = 0
        for number in range(int(low), int(high) + 1):
            self.enumerate_visits += 1
            if self._independent_check(condition, arg, number):
                total += 1
        return total

    def independent_minimum(self, condition, arg=None, low=None, high=None):
        """独立做法二：针对具体数查询的逐数枚举，独立成路。"""
        low, high = self._pick_range(low, high)
        self._reset_counts()
        for number in range(int(low), int(high) + 1):
            self.enumerate_visits += 1
            if self._independent_check(condition, arg, number):
                return number
        return None

    def _independent_check(self, condition, arg, number):
        """独立口味的条件判定，不复用主路径的判定函数。"""
        if not isinstance(condition, str):
            raise ParamErro("条件名必须是字符串：%r" % (condition,))
        texts = self._digits_of(number)
        if condition == "without_digit":
            if not _is_int(arg) or arg < 0 or arg >= 10:
                raise ValueErro("目标数字必须是零到九之间的整数：%r" % (arg,))
            return arg not in texts
        if condition == "digit_sum":
            if not _is_int(arg) or arg < 0:
                raise ValueErro("数字和必须是不小于零的整数：%r" % (arg,))
            return sum(texts) == arg
        if condition == "strict_increasing":
            for i in range(len(texts) - 1):
                if texts[i] >= texts[i + 1]:
                    return False
            return True
        if condition == "multiple":
            if not _is_int(arg) or arg < 0:
                raise ValueErro("倍数底数必须是不小于零的整数：%r" % (arg,))
            if arg == 0:
                raise ValueErro("倍数底数不得为零")
            return int(number) % arg == 0
        raise ParamErro("不认识的条件名：%r" % (condition,))

    # -------------------------------------------------------- 规模计数

    @property
    def range_width(self):
        """当前区间的整数个数。"""
        return int(self._high) - int(self._low) + 1

    @property
    def digits(self):
        """当前上界的位数。"""
        return self._digits
