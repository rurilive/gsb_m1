"""mqdp 改造前的朴素基线：窗口约束动态规划的逐前驱枚举。

本模块只用最直白的循环完成一族一维状态转移：每个前缀从一段长度为固定窗口
的前驱区间里把每个允许的前驱挨个看一遍，取转移值的最小或最大，规模一大就
慢，但结果对。窗口长度为一的平凡情形也不做任何优化，照样把唯一前驱完整走
一遍。异常统一挂在 ``MqdpErro`` 之下。纯标准库，无外部依赖。
"""


class MqdpErro(ValueError):
    """mqdp 全部异常的基类，继承自内建 ValueError。"""


class WindowErro(MqdpErro):
    """窗口长度不是正整数。"""


class CoefErro(MqdpErro):
    """转移系数或规模参数不是合法整数。"""


class DataErro(MqdpErro):
    """输入的项序列不是合法的可迭代整数序列。"""


MIN_POLICY = "min"
MAX_POLICY = "max"
_POLICIES = (MIN_POLICY, MAX_POLICY)


def _as_terms(terms):
    """把输入拷成一个新的整数列表，非序列或含非整数项时按包内异常拒绝。"""
    if isinstance(terms, (str, bytes)):
        raise DataErro("terms must be an iterable of integers, got %r" % (terms,))
    try:
        seq = list(terms)
    except TypeError:
        raise DataErro("terms must be an iterable of integers, got %r" % (terms,))
    out = []
    for item in seq:
        if isinstance(item, bool) or not isinstance(item, int):
            raise DataErro("every term must be an integer, got %r" % (item,))
        out.append(item)
    return out


def _check_window(window):
    """窗口长度必须是正整数，否则快速失败。"""
    if isinstance(window, bool) or not isinstance(window, int):
        raise WindowErro("window must be a positive integer, got %r" % (window,))
    if window <= 0:
        raise WindowErro("window must be a positive integer, got %r" % (window,))
    return window


def _check_coef(coef):
    """转移系数必须是整数。"""
    if isinstance(coef, bool) or not isinstance(coef, int):
        raise CoefErro("coef must be an integer, got %r" % (coef,))
    return coef


def _check_policy(policy):
    """转移口径只允许取最小或取最大。"""
    if not isinstance(policy, str):
        raise MqdpErro("policy must be a string, got %r" % (policy,))
    if policy not in _POLICIES:
        raise MqdpErro("unknown policy %r" % (policy,))
    return policy


def _better(policy, candidate, best):
    """候选是否严格优于当前最优；并列时返回假，保持先出现的那个，即下标较小者。"""
    if policy == MIN_POLICY:
        return candidate < best
    return candidate > best


class WindowDP:
    """一维窗口约束动态规划的朴素实现，是双端队列优化版改造前的基线。

    状态定义：下标为零处的前缀值固定为零；下标大于零处的前缀值为该前缀的
    最优转移值。

    转移定义：下标为 ``index`` 处的前缀值，等于转移系数乘以序列里第 ``index``
    项，再加上前驱区间内全部前驱前缀值里的最优。允许的前驱区间是当前下标往
    前最多 ``window`` 个位置，即 ``[index - window, index)`` 与下标零一侧取交；
    窗口长度为一的平凡情形同样逐前驱完整枚举。前缀值并列时取下标较小的前驱。

    :param window: 窗口长度，正整数
    :param coef: 转移系数，整数
    :param policy: 转移口径，``min`` 取最小、``max`` 取最大
    """

    def __init__(self, window, coef=1, policy=MIN_POLICY):
        self._window = _check_window(window)
        self._coef = _check_coef(coef)
        self._policy = _check_policy(policy)

    @property
    def window(self):
        return self._window

    @property
    def coef(self):
        return self._coef

    @property
    def policy(self):
        return self._policy

    def _resolve(self, coef, policy):
        """把单次调用可覆盖的系数与口径解析成一次调用要用的值。"""
        if coef is None:
            coef = self._coef
        else:
            coef = _check_coef(coef)
        if policy is None:
            policy = self._policy
        else:
            policy = _check_policy(policy)
        return coef, policy

    def _bounds(self, index, length):
        """当前下标允许的前驱区间；窗口长度为一就是独一个前驱。"""
        start = index - self._window
        if start < 0:
            start = 0
        return start, index

    def _run(self, values, coef, policy):
        """按正向下标序逐前缀枚举前驱，返回前缀值表与每个前缀选中的前驱下标。"""
        length = len(values)
        table = [0] * (length + 1)
        steps = [0] * (length + 1)
        for index in range(1, length + 1):
            start, end = self._bounds(index, length)
            best_value = None
            best_index = start
            for predecessor in range(start, end):
                candidate = coef * values[index - 1] + table[predecessor]
                if best_value is None or _better(policy, candidate, best_value):
                    best_value = candidate
                    best_index = predecessor
            table[index] = best_value
            steps[index] = best_index
        return table, steps

    def _scan(self, values, coef, policy):
        """另起一条独立做法：把窗口完整切片出来再逐个枚举，用于交叉对照。"""
        length = len(values)
        table = [0] * (length + 1)
        for index in range(1, length + 1):
            start, end = self._bounds(index, length)
            window = [predecessor for predecessor in range(start, end)]
            best_value = None
            for predecessor in window:
                candidate = coef * values[index - 1] + table[predecessor]
                if best_value is None or _better(policy, candidate, best_value):
                    best_value = candidate
            table[index] = best_value
        return table

    def forward(self, terms, coef=None, policy=None):
        """按正向下标序把前缀值逐个算出来，返回长度等于项数加一的列表。"""
        values = _as_terms(terms)
        coef, policy = self._resolve(coef, policy)
        table, _ = self._run(values, coef, policy)
        return table

    def window_scan(self, terms, coef=None, policy=None):
        """独立窗口枚举口径下的前缀值表，与 ``forward`` 结果必须逐项相同。"""
        values = _as_terms(terms)
        coef, policy = self._resolve(coef, policy)
        return self._scan(values, coef, policy)

    def steps(self, terms, coef=None, policy=None):
        """每个前缀选中的前驱下标表，长度等于项数加一；并列时取下标较小者。"""
        values = _as_terms(terms)
        coef, policy = self._resolve(coef, policy)
        _, steps = self._run(values, coef, policy)
        return steps

    def answer(self, terms, coef=None, policy=None):
        """末尾前缀值，即整个序列的转移最优；空序列返回零。"""
        table = self.forward(terms, coef, policy)
        return table[-1]

    def matches(self, terms, coef=None, policy=None):
        """正序口径与独立窗口枚举口径在同一批数据上是否逐项一致。"""
        values = _as_terms(terms)
        coef, policy = self._resolve(coef, policy)
        table, _ = self._run(values, coef, policy)
        return table == self._scan(values, coef, policy)

    def compare_count(self, size):
        """逐前驱枚举在规模为 ``size`` 时的转移比较次数。

        每个下标把允许前驱区间里的每个前驱都看一遍，窗口长度为一的平凡情形
        也不优化；窗口不小于一时代价为规模乘规模减一的一半。
        """
        if isinstance(size, bool) or not isinstance(size, int):
            raise CoefErro("size must be an integer, got %r" % (size,))
        if size < 0:
            raise CoefErro("size must be non-negative, got %r" % (size,))
        return size * (size - 1) // 2
