"""lcsalign.sequence: 改造前的朴素序列比对实现。

现有能力只有一项：按最直白的方式枚举第一个序列的全部子序列，逐个判断它
是不是第二个序列的子序列，取其中最长的那个。结果正确，但子序列条数随序列
长度指数级增长，稍长一点的输入就慢到无法忍受。
"""


class SequenceError(Exception):
    """本包异常的基类。现有实现只用到它自身。"""


class EmptySequenceError(SequenceError):
    """长度为零的序列不能参与比对。"""


def _check_pair(a, b):
    if not a or not b:
        raise EmptySequenceError("参与比对的序列不能为空")
    return list(a), list(b)


def _all_subsequences(seq):
    """列出 seq 的全部子序列，按长度从大到小、同长按下标元组字典序。

    枚举方式是最朴素的递归：对每个位置决定取或不取。返回的是元素列表，
    每个元素对应一种取法，顺序由递归的取先分支保证为反字典序，
    这里再统一按长度降序、下标元组升序排一次，作为对外稳定的顺序。
    """
    items = []
    n = len(seq)

    def walk(start, chosen):
        if start == n:
            items.append(list(chosen))
            return
        chosen.append(seq[start])
        walk(start + 1, chosen)
        chosen.pop()
        walk(start + 1, chosen)

    walk(0, [])
    return items


def _is_subsequence(sub, seq):
    """判断 sub 是否为 seq 的子序列（不要求连续），最直白的双指针。"""
    it = iter(seq)
    return all(any(x == y for y in it) for x in sub)


def _index_of(sub, seq):
    """给出 sub 作为 seq 子序列的一组下标，取最靠前的那种搭配。"""
    idx = []
    pos = 0
    for x in sub:
        while pos < len(seq) and seq[pos] != x:
            pos += 1
        if pos == len(seq):
            return None
        idx.append(pos)
        pos += 1
    return idx


def _rank_key(candidate, a):
    """同长度候选的稳定次序键：下标元组字典序最小者胜出。"""
    idx = _index_of(candidate, a)
    if idx is None:
        idx = list(range(len(candidate)))
    return (idx, candidate)


def lcs_length(a, b):
    """用枚举全部子序列的朴素做法求最长公共子序列的长度。"""
    a, b = _check_pair(a, b)
    best = 0
    for sub in _all_subsequences(a):
        if len(sub) <= best:
            continue
        if _is_subsequence(sub, b):
            best = len(sub)
    return best


def lcs_sequence(a, b):
    """用枚举全部子序列的朴素做法求最长公共子序列的具体元素。

    没有公共元素时返回空列表；有多个同长度的公共子序列时，取按当前位置
    最靠前的那种搭配下的字典序最小者。这个取法在改造前就是写死的口径。
    """
    a, b = _check_pair(a, b)
    best = []
    for sub in _all_subsequences(a):
        if len(sub) < len(best):
            continue
        if not _is_subsequence(sub, b):
            continue
        if len(sub) > len(best):
            best = list(sub)
        else:
            if _rank_key(sub, a) < _rank_key(best, a):
                best = list(sub)
    return best


def summary(a, b):
    """给出一对标量摘要：长度与具体子序列，供演示与交叉核对使用。"""
    return {"length": lcs_length(a, b), "sequence": lcs_sequence(a, b)}
