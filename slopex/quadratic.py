"""slopex 改造前的朴素基线：划分型动态规划的平方枚举实现。

本模块只用最直白的双重循环完成一族把序列前若干项切成若干连续段、
让各段代价之和取最小的划分问题，规模一大就慢，但结果对。
异常统一挂在 ``SlopexError`` 之下。纯标准库，无外部依赖。
"""


class SlopexError(ValueError):
    """slopex 全部异常的基类，继承自内建 ValueError。"""


class InvalidPolicyError(SlopexError):
    """代价策略名非法。"""


class InvalidWeightError(SlopexError):
    """代价相关的系数或规模参数非法。"""


class InvalidSequenceError(SlopexError):
    """输入的序列不是合法的可迭代非负整数序列。"""


INFINITY = float("inf")

# 支持的两种代价策略。
SQUARE_POLICY = "square"
POSITION_POLICY = "position"
_POLICIES = (SQUARE_POLICY, POSITION_POLICY)


class SegmentPlanner:
    """把序列切成若干连续段，用双重循环枚举最后一段的起点求最小总代价。

    重量为段内各元素之和，长度为段内元素个数，起点为段的起始下标。两种
    策略的单段代价为：

    - ``square``：重量平方再加固定的每段开销
    - ``position``：重量乘以起点下标加一再加固定的每段开销

    固定的每段开销由构造参数给出，每多切一段就多付一次；开销大时倾向
    少切，开销小时倾向多切，最优划分随序列与开销而变。所有求值方法都
    自建局部状态，不依赖任何模块级可变状态。

    :param policy: 代价策略名，取 ``square`` 或 ``position``
    :param coef: 每段的固定开销，非负整数
    """

    def __init__(self, policy=SQUARE_POLICY, coef=2):
        if not isinstance(policy, str):
            raise InvalidPolicyError("策略名必须是字符串，收到 %r" % (policy,))
        if policy not in _POLICIES:
            raise InvalidPolicyError("未知的策略名 %r" % (policy,))
        if isinstance(coef, bool) or not isinstance(coef, int):
            raise InvalidWeightError("开销必须是整数，收到 %r" % (coef,))
        if coef < 0:
            raise InvalidWeightError("开销必须是非负整数，收到 %d" % (coef,))
        self._policy = policy
        self._coef = coef

    @property
    def policy(self):
        return self._policy

    @property
    def coef(self):
        return self._coef

    def segment_cost(self, weight, length, start=0):
        """单段代价：重量为段内各元素之和，长度为段内元素个数，起点为起始下标。"""
        if isinstance(weight, bool) or not isinstance(weight, int):
            raise InvalidWeightError("重量必须是整数，收到 %r" % (weight,))
        if isinstance(length, bool) or not isinstance(length, int):
            raise InvalidWeightError("长度必须是整数，收到 %r" % (length,))
        if isinstance(start, bool) or not isinstance(start, int):
            raise InvalidWeightError("起点必须是整数，收到 %r" % (start,))
        if weight < 0:
            raise InvalidWeightError("重量不能为负，收到 %d" % (weight,))
        if length <= 0:
            raise InvalidWeightError("长度必须是正整数，收到 %d" % (length,))
        if start < 0:
            raise InvalidWeightError("起点不能为负，收到 %d" % (start,))
        if self._policy == SQUARE_POLICY:
            return weight * weight + self._coef
        return weight * (start + 1) + self._coef

    def _collect(self, seq):
        try:
            values = list(seq)
        except TypeError as exc:
            raise InvalidSequenceError("输入不可迭代：%s" % (exc,))
        for item in values:
            if isinstance(item, bool) or not isinstance(item, int):
                raise InvalidSequenceError("序列元素必须是整数，收到 %r" % (item,))
            if item < 0:
                raise InvalidSequenceError("序列元素不能为负，收到 %d" % (item,))
        return values

    def _dp_table(self, values):
        """自建前缀表与动态规划表，返回 dp 与切点选择表。

        状态：dp[i] 表示前 i 项切成若干段的最小累计代价。
        转移：枚举最后一段的起点 j，dp[i] 取 dp[j] 加上段 (j, i] 的代价。
        并列时取起点最小的那一段，保证确定性。
        """
        n = len(values)
        prefix = [0] * (n + 1)
        for i in range(n):
            prefix[i + 1] = prefix[i] + values[i]
        dp = [INFINITY] * (n + 1)
        choice = [0] * (n + 1)
        dp[0] = 0
        for i in range(1, n + 1):
            best = INFINITY
            pick = 0
            for j in range(0, i):
                weight = prefix[i] - prefix[j]
                length = i - j
                cost = dp[j] + self.segment_cost(weight, length, j)
                if cost < best:
                    best = cost
                    pick = j
            dp[i] = best
            choice[i] = pick
        return dp, choice

    def best_partition(self, seq):
        """最优划分的最小总代价，空序列返回 0。"""
        values = self._collect(seq)
        if not values:
            return 0
        dp, _ = self._dp_table(values)
        return dp[len(values)]

    def best_partitions(self, seq):
        """每个前缀的最优代价序列，下标 i 对应前 i 项，长度为项数加一。"""
        values = self._collect(seq)
        dp, _ = self._dp_table(values)
        return dp

    def best_cut_points(self, seq):
        """取到最优划分时的各段切点列表，空序列返回空表。"""
        values = self._collect(seq)
        if not values:
            return []
        _, choice = self._dp_table(values)
        cuts = []
        i = len(values)
        while i > 0:
            cuts.append(choice[i])
            i = choice[i]
        cuts.reverse()
        return cuts

    def compare_count(self, n):
        """平方枚举在规模为 n 时的转移比较次数，等于 n 乘 n 加一的一半。"""
        if isinstance(n, bool) or not isinstance(n, int):
            raise InvalidWeightError("规模必须是整数，收到 %r" % (n,))
        if n < 0:
            raise InvalidWeightError("规模不能为负，收到 %d" % (n,))
        return n * (n + 1) // 2

    def __repr__(self):
        return "SegmentPlanner(policy=%r, coef=%r)" % (self._policy, self._coef)
