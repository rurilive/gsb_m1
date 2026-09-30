"""intervaldp.interval: 区间划分与括号匹配的朴素实现（改造前基线）。

围绕区间与括号串做四件最基础的事：

  - merge_cost   合并石子：对每个区间枚举全部分裂点，把左右两半的最优代价
                 相加再加上本区间石子重量，取最小。递归枚举全部划分，结果对
                 但每一步都把子区间重算一遍，长度一长就是立方甚至更高量级；
  - best_split   最优划分：用同样的方式找出把一段区间切成两段的最优分裂点，
                 返回分裂点本身以体现划分的骨架；
  - longest_valid 括号匹配：判定一个子串是否合法时用栈逐字符扫描，并且对每个
                 子串都从头重新扫一遍，全部子串枚举下来是平方量级；
  - min_add      最少添加：对每个区间枚举全部分裂点，把左右两半各自的最少添加
                 数相加，若两端恰好是一对匹配括号则再减去二，取最小；不缓存，
                 长度一长就是立方或者更高量级，但结果是对的。

这些做法直观可靠，结果一眼能看穿；规模一长就是立方或平方量级地退化。
本文件是改造前的基线，朴素路径在改造之后不得删除，新实现必须与它对同一批
数据给出的事实逐项对齐，并对同一批输入逐项一致。

异常统一继承 IntervalErro 基类：TextErro / StoneErro / CostErro。
"""


class IntervalErro(Exception):
    """区间划分与括号匹配工具包所有异常的基类，非法输入一律快速失败。"""


class TextErro(IntervalErro):
    """括号串非法：为空、元素不是单个字符、出现方括号圆括号花括号之外的字符。"""


class StoneErro(IntervalErro):
    """石子序列非法：为空、元素不是整数、出现负数。"""


class CostErro(IntervalErro):
    """代价非法：合并代价不是非负整数。"""


_OPENERS = "([{"
_CLOSERS = ")]}"
_PAIRS = {")": "(", "]": "[", "}": "{"}


def _check_text(text):
    """把入参规整成字符串并校验，非法即抛 TextErro。"""
    if not isinstance(text, str):
        raise TextErro("括号串必须是字符串，收到 %r" % (text,))
    for ch in text:
        if ch not in "()[]{}":
            raise TextErro("括号串只允许圆括号方括号花括号，收到 %r" % (ch,))
    return text


def _normalize_stones(stones):
    """把入参规整成非负整数列表，非法即抛 StoneErro。"""
    try:
        items = list(stones)
    except TypeError:
        raise StoneErro("石子序列必须是可迭代对象，收到 %r" % (stones,))
    if len(items) == 0:
        raise StoneErro("石子序列不能为空")
    out = []
    for v in items:
        if isinstance(v, bool) or not isinstance(v, int):
            raise StoneErro("石子重量必须是整数，收到 %r" % (v,))
        if v < 0:
            raise StoneErro("石子重量不能为负，收到 %r" % (v,))
        out.append(int(v))
    return out


def _check_cost(cost_each):
    if isinstance(cost_each, bool) or not isinstance(cost_each, int):
        raise CostErro("合并代价必须是非负整数，收到 %r" % (cost_each,))
    if cost_each < 0:
        raise CostErro("合并代价必须是非负整数，收到 %r" % (cost_each,))
    return int(cost_each)


def _prefix(stones):
    """前缀和，width(lo, hi) 取 stones[lo:hi] 之和。"""
    pre = [0]
    for v in stones:
        pre.append(pre[-1] + v)
    return pre


def _width(pre, lo, hi):
    return pre[hi] - pre[lo]


def _is_valid(text, lo, hi):
    """用栈逐字符扫描 text[lo:hi]，判定是否为合法括号串。"""
    stack = []
    for ch in text[lo:hi]:
        if ch in _OPENERS:
            stack.append(ch)
        else:
            want = _PAIRS[ch]
            if not stack or stack[-1] != want:
                return False
            stack.pop()
    return not stack


def _is_matched_pair(text, lo, hi):
    """text[lo] 与 text[hi-1] 是否恰好构成一对匹配括号。"""
    if hi - lo < 2:
        return False
    return _PAIRS.get(text[hi - 1]) == text[lo]


def _naive_add(text, lo, hi, counter):
    """区间 [lo, hi) 调整为合法括号串所需的最少添加数，递归枚举全部分裂点。

    逐个分裂点把左右两半的最少添加数各自重新递归算一遍再加起来；若本区间的
    两端恰好是一对匹配括号，则这一对连起来可以省去，对应取内部区间的最少
    添加数，两者取最小。不做缓存，区间一长就是立方甚至更高量级，但结果是对的。
    """
    if hi - lo <= 1:
        return hi - lo
    best = None
    for mid in range(lo + 1, hi):
        counter[0] += 1
        total = _naive_add(text, lo, mid, counter) + _naive_add(text, mid, hi, counter)
        if best is None or total < best:
            best = total
    if _is_matched_pair(text, lo, hi):
        inner = _naive_add(text, lo + 1, hi - 1, counter)
        if inner < best:
            best = inner
    return best


def _naive_cost(stones, pre, cost_each, lo, hi, counter):
    """区间 [lo, hi) 合并成一堆的最小代价，递归枚举全部分裂点。

    每次枚举到分裂点 k 就把左右两半的代价各自重新递归算一遍，不做任何缓存，
    区间一长就立方甚至更高量级地退化，但结果是对的。
    """
    if hi - lo <= 1:
        return 0
    best = None
    for k in range(lo + 1, hi):
        counter[0] += 1
        left = _naive_cost(stones, pre, cost_each, lo, k, counter)
        right = _naive_cost(stones, pre, cost_each, k, hi, counter)
        total = left + right + cost_each * _width(pre, lo, hi)
        if best is None or total < best:
            best = total
    return best


class IntervalKit:
    """区间划分与括号匹配朴素工具集（改造前基线）。

    每次调用都把上一次的枚举次数归零后重新累加，实例本身不保存任何跨调用的
    派生状态；同一批输入连续调用两次，结果与计数都应逐位一致。
    """

    def __init__(self):
        # 本次调用朴素路径实际枚举的分裂点次数，进入调用前归零后重新累加。
        self.split_visits = 0
        # 本次调用为括号判定所做的逐字符扫描次数。
        self.char_visits = 0

    # ----------------------------------------------------------------
    # 合并石子：对每个区间枚举全部分裂点求最优再合并
    # ----------------------------------------------------------------
    def merge_cost(self, stones, cost_each=1, lo=None, hi=None):
        """把 stones 合并成一堆的最小代价，每步合并的代价是两段石子重量之和。

        cost_each 是单位重量的合并代价，默认一。lo 与 hi 可指定只合并
        stones[lo:hi] 这一段，缺省合并整段。枚举全部分裂点，结果正确。
        石子序列非法抛 StoneErro，代价非法抛 CostErro。
        """
        self.split_visits = 0
        vals = _normalize_stones(stones)
        unit = _check_cost(cost_each)
        n = len(vals)
        if lo is None:
            lo = 0
        if hi is None:
            hi = n
        if lo < 0 or hi > n or lo > hi:
            raise StoneErro("区间范围越界：lo=%r hi=%r n=%r" % (lo, hi, n))
        pre = _prefix(vals)
        counter = [0]
        best = _naive_cost(vals, pre, unit, lo, hi, counter)
        self.split_visits = counter[0]
        return best

    # ----------------------------------------------------------------
    # 最优划分：枚举分裂点找出把区间切成两段的最优位置
    # ----------------------------------------------------------------
    def best_split(self, stones, cost_each=1):
        """返回把整段石子切一刀的最优分裂点。

        分裂点 k 表示切成 [0, k) 与 [k, n) 两段，取两段各自最优合并代价之和
        最小的 k；并列时取最小的 k。枚举全部分裂点，结果正确。
        """
        self.split_visits = 0
        vals = _normalize_stones(stones)
        unit = _check_cost(cost_each)
        n = len(vals)
        if n < 2:
            raise StoneErro("至少需要两颗石子才能划分，收到 %r 颗" % (n,))
        pre = _prefix(vals)
        best_k = None
        best_cost = None
        for k in range(1, n):
            counter = [0]
            left = _naive_cost(vals, pre, unit, 0, k, counter)
            right = _naive_cost(vals, pre, unit, k, n, counter)
            self.split_visits += counter[0]
            total = left + right
            if best_cost is None or total < best_cost:
                best_cost = total
                best_k = k
        return best_k

    # ----------------------------------------------------------------
    # 括号匹配：对每个子串从头用栈重新扫描
    # ----------------------------------------------------------------
    def longest_valid(self, text):
        """最长合法子串的长度。

        合法指括号正确配对且嵌套。对每个子串都从头用栈重新扫一遍，把合法的
        子串长度取最大；空串或没有合法子串时返回零。非法输入抛 TextErro。
        """
        self.char_visits = 0
        s = _check_text(text)
        n = len(s)
        best = 0
        for lo in range(n):
            for hi in range(lo + 1, n + 1):
                self.char_visits += hi - lo
                if _is_valid(s, lo, hi):
                    length = hi - lo
                    if length > best:
                        best = length
        return best

    def min_add(self, text):
        """使整个串合法所需添加的最少括号数。

        对整串枚举全部分裂点，把左右两半各自的最少添加数相加，若两端恰好是
        一对匹配括号则可以再减去二，取最小。空串返回零。非法输入抛 TextErro。
        """
        self.split_visits = 0
        s = _check_text(text)
        n = len(s)
        if n == 0:
            return 0
        counter = [0]
        best = _naive_add(s, 0, n, counter)
        self.split_visits = counter[0]
        return best
