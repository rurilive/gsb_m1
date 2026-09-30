"""votehal 的朴素频次统计工具（改造前的现状）。

现在只有一条路：求多数元素时对每个候选把整条序列从头再扫一遍数出现
次数，两两比较是平方量级；求超过元素种类数分之一的众数时枚举全部候选
逐个重扫；求前几频繁元素与判断是否存在多数元素也靠反复重扫或全排序。
结果都对，但规模一大就慢。线性做法见任务描述。
"""


class Erro(Exception):
    """本模块所有对外异常的公共基类。"""


class VoteError(Erro):
    """序列或参数的非法输入。"""


def _check_seq(seq):
    """序列必须是列表或元组，元素不限，允许为空。"""
    if not isinstance(seq, (list, tuple)):
        raise VoteError("seq must be a list or tuple")
    return seq


def _check_k(k):
    """k 必须是大于等于一的整数。"""
    if not isinstance(k, int) or isinstance(k, bool):
        raise VoteError("k must be an int")
    if k < 1:
        raise VoteError("k must be at least 1")
    return k


def _check_top_n(n):
    """n 必须是大于等于零的整数。"""
    if not isinstance(n, int) or isinstance(n, bool):
        raise VoteError("n must be an int")
    if n < 0:
        raise VoteError("n must be at least 0")
    return n


def naive_counts(seq):
    """对每个不同的元素，把整条序列从头再扫一遍数它的出现次数。

    返回一个元素到次数的字典，并把每个不同元素对序列的一次完整重扫
    记为一次扫描。结果与出现顺序无关。
    """
    _check_seq(seq)
    counts = {}
    for value in seq:
        if value not in counts:
            hit = 0
            for item in seq:
                if item == value:
                    hit += 1
            counts[value] = hit
    return counts


def count_value(seq, value):
    """把序列从头扫一遍，数出某个值的出现次数。"""
    _check_seq(seq)
    hit = 0
    for item in seq:
        if item == value:
            hit += 1
    return hit


def majority_value(seq, counts=None):
    """多数元素的第一个取值，没有多数元素时返回空。

    对每个不同的元素重扫整条序列得到次数，再逐个与阈值比较，命中即返回。
    """
    _check_seq(seq)
    if not seq:
        return None
    threshold = len(seq) // 2
    if counts is None:
        counts = naive_counts(seq)
    for value in counts:
        if counts[value] > threshold:
            return value
    return None


def majority_count(seq, counts=None):
    """多数元素的出现次数，没有多数元素时为零。"""
    _check_seq(seq)
    value = majority_value(seq, counts)
    if value is None:
        return 0
    if counts is not None:
        return counts[value]
    return count_value(seq, value)


def has_majority(seq, counts=None):
    """序列里是否存在出现次数超过一半的多数元素。"""
    return majority_value(seq, counts) is not None


def frequent_values(seq, k, counts=None):
    """出现次数超过元素种类数分之一的全部元素，按值升序给出。

    枚举全部候选，对每个候选重扫序列数次数，再筛掉不达标的。
    """
    _check_seq(seq)
    _check_k(k)
    if not seq:
        return []
    threshold = len(seq) // k
    if threshold < 1:
        threshold = 1
    if counts is None:
        counts = naive_counts(seq)
    out = []
    for value in counts:
        if counts[value] > threshold:
            out.append(value)
    out.sort()
    return out


def top_frequent(seq, n):
    """出现次数排前 n 的元素，返回次数与值配成的对。

    按次数从多到少排，次数相同按值从小到大排，并列时口径固定。
    """
    _check_seq(seq)
    _check_top_n(n)
    if n == 0:
        return []
    counts = naive_counts(seq)
    items = [(hit, value) for value, hit in counts.items()]
    items.sort(key=lambda pair: (-pair[0], pair[1]))
    return items[:n]


def visit_count(seq):
    """朴素做法对序列的完整重扫次数，即不同元素的个数。"""
    _check_seq(seq)
    distinct = 0
    seen = []
    for value in seq:
        if value not in seen:
            seen.append(value)
            distinct += 1
    return distinct


class VoteTools:
    """绑定一条序列的频次统计工具，只有重扫这一条路。

    每个方法都按最直白的循环完成，并把对序列的完整重扫次数与逐元素比较
    次数累计进计数器，供与线性做法对照规模。序列在构造时校验并固定。
    """

    def __init__(self, seq):
        self._seq = list(_check_seq(seq))
        self._rescan_count = 0
        self._visit_count = 0

    def seq(self):
        """返回绑定的序列（副本）。"""
        return list(self._seq)

    def reset_rescan_count(self):
        """把完整重扫计数与逐元素比较计数清零。"""
        self._rescan_count = 0
        self._visit_count = 0

    def rescan_count(self):
        """自上次清零以来累计完整重扫了多少遍序列。"""
        return self._rescan_count

    def visit_count(self):
        """自上次清零以来累计比较了多少个元素位置。"""
        return self._visit_count

    def _note_rescan(self):
        self._rescan_count += 1

    def counts(self):
        """对每个不同元素重扫一遍序列数次数，累计重扫与比较次数。"""
        seq = self._seq
        result = {}
        for value in seq:
            if value in result:
                continue
            self._note_rescan()
            hit = 0
            for item in seq:
                self._visit_count += 1
                if item == value:
                    hit += 1
            result[value] = hit
        return result

    def majority(self):
        """多数元素取值与出现次数配成的对，没有时返回空对。

        累计重扫次数，供与线性做法对照规模。
        """
        counts = self.counts()
        if not counts:
            return (None, 0)
        threshold = len(self._seq) // 2
        for value in counts:
            if counts[value] > threshold:
                return (value, counts[value])
        return (None, 0)

    def top(self, n):
        """前 n 频繁元素，按次数降序、次数相同按值升序。"""
        items = [(hit, value) for value, hit in self.counts().items()]
        items.sort(key=lambda pair: (-pair[0], pair[1]))
        return items[:n]


def two_pass_majority(seq):
    """两遍做法：先一趟哈希统计频次，再一趟按原序确认多数元素。

    第一遍逐元素累加进字典，第二遍按原序列顺序找出第一个出现次数超过
    一半的值，命中即返回。两趟合计的逐元素访问次数与序列长度成正比。
    """
    _check_seq(seq)
    counts = {}
    for value in seq:
        counts[value] = counts.get(value, 0) + 1
    threshold = len(seq) // 2
    visited = len(seq)
    best_value = None
    best_count = 0
    for value in seq:
        hit = counts[value]
        visited += 1
        if hit > threshold:
            best_value = value
            best_count = hit
            break
    return (best_value, best_count, visited)
