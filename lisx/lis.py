"""lisx.lis: 最长上升子序列的朴素实现（改造前基线）。

围绕一个整数序列做三件最基础的事：

  - length    长度：对每个位置向前枚举全部更小的位置，取其中已经算出的
              最长上升子序列长度的最大值再加一，全部位置取最大；
  - count     个数：枚举全部子序列，逐个判定它是否严格上升，把上升的计数；
  - rebuild   重建：先算出每个位置结尾的最长上升子序列长度，再从尾部找长度
              等于全局最大值的位置往回逐个回溯，拼出一条方案。

这些做法直观可靠，结果一眼能看穿；序列一长就是平方甚至指数量级地退化。
本文件是改造前的基线，朴素路径在改造之后不得删除，新实现必须与它对同一批
数据给出的事实逐项对齐。

异常统一继承 LisErro 基类：SeqErro / ModeErro。
"""


class LisErro(Exception):
    """最长上升子序列工具包所有异常的基类，非法输入一律快速失败。"""


class SeqErro(LisErro):
    """序列非法：为空、元素不是整数、长度为负。"""


class ModeErro(LisErro):
    """模式非法：不是严格上升或非下降两种口径之一。"""


def _as_int(v, where):
    """把入参规整成 int，非法即抛 SeqErro。"""
    if isinstance(v, bool) or not isinstance(v, int):
        raise SeqErro("%s: 元素必须是整数，收到 %r" % (where, v))
    return int(v)


def _normalize(seq):
    """把入参规整成整数列表，非法即抛 SeqErro；同时拒绝非有限长度。"""
    try:
        items = list(seq)
    except TypeError:
        raise SeqErro("序列必须是可迭代对象，收到 %r" % (seq,))
    return [_as_int(v, "序列") for v in items]


def _check_mode(mode):
    if mode not in ("strict", "nondecreasing"):
        raise ModeErro("模式必须是 strict 或 nondecreasing，收到 %r" % (mode,))


def _dp_len(vals, mode):
    """每个位置结尾的最长上升子序列长度（朴素平方）。"""
    n = len(vals)
    dp = [1] * n
    for i in range(n):
        best = 0
        for j in range(i):
            if mode == "strict":
                ok = vals[j] < vals[i]
            else:
                ok = vals[j] <= vals[i]
            if ok and dp[j] > best:
                best = dp[j]
        dp[i] = best + 1
    return dp


class LisKit:
    """最长上升子序列朴素工具集（改造前基线）。

    每次调用都把上一次的比较次数归零后重新累加，实例本身不保存任何跨调用的
    派生状态；同一批输入连续调用两次，结果与计数都应逐位一致。
    """

    def __init__(self):
        # 本次调用实际发生的两两比较次数，进入调用前归零后重新累加。
        self.comparisons = 0
        # 本次调用为重建方案所做的比较次数。
        self.rebuild_comparisons = 0

    # ----------------------------------------------------------------
    # 长度：每个位置向前枚举全部更小的位置累加，再取最大
    # ----------------------------------------------------------------
    def length(self, seq, mode="strict"):
        """最长上升子序列的长度。

        严格上升要求后一项严格大于前一项，非下降允许相等。空序列返回零；
        单元素返回一。元素不是整数抛 SeqErro，模式不是两种口径之一抛 ModeErro。
        """
        self.comparisons = 0
        _check_mode(mode)
        vals = _normalize(seq)
        n = len(vals)
        if n == 0:
            return 0
        dp = [1] * n
        for i in range(n):
            best = 0
            for j in range(i):
                self.comparisons += 1
                if mode == "strict":
                    ok = vals[j] < vals[i]
                else:
                    ok = vals[j] <= vals[i]
                if ok and dp[j] > best:
                    best = dp[j]
            dp[i] = best + 1
        return max(dp)

    # ----------------------------------------------------------------
    # 个数：枚举全部子序列，逐个判定是否上升
    # ----------------------------------------------------------------
    def count(self, seq, mode="strict"):
        """上升子序列的个数，含全部长度（按下标集计，值相同但下标不同算不同）。

        空序列计一个（空子序列）。用位掩码枚举全部子序列并逐个判定是否上升，
        规模一长就指数级退化。非法输入抛 SeqErro / ModeErro。
        """
        _check_mode(mode)
        vals = _normalize(seq)
        n = len(vals)
        total = 0
        for mask in range(1 << n):
            picked = [vals[i] for i in range(n) if (mask >> i) & 1]
            if self._is_ascending(picked, mode):
                total += 1
        return total

    @staticmethod
    def _is_ascending(picked, mode):
        for t in range(1, len(picked)):
            if mode == "strict":
                if not picked[t - 1] < picked[t]:
                    return False
            else:
                if not picked[t - 1] <= picked[t]:
                    return False
        return True

    # ----------------------------------------------------------------
    # 重建：先算长度，再从尾部逐个回溯拼出一条方案
    # ----------------------------------------------------------------
    def rebuild(self, seq, mode="strict"):
        """重建一条最长上升子序列，返回下标序列（严格递增）与对应值序列。

        方案只需合法：下标严格递增，相邻值满足模式口径，总长等于 length。
        存在并列时取结尾最靠右、每个前驱也取最靠右的那一条。空序列返回空
        方案。非法输入抛 SeqErro / ModeErro。
        """
        self.rebuild_comparisons = 0
        _check_mode(mode)
        vals = _normalize(seq)
        n = len(vals)
        if n == 0:
            return ([], [])
        dp = _dp_len(vals, mode)
        target = max(dp)
        idx = None
        # 从尾部找第一个长度等于全局最大值的位置：取该位置结尾，回溯时
        # 再在每个更小的位置里挑最靠右的合法前驱，叠起来即字典序最小的方案。
        for i in range(n - 1, -1, -1):
            self.rebuild_comparisons += 1
            if dp[i] == target:
                idx = i
                break
        order = []
        cur = idx
        while cur is not None:
            order.append(cur)
            if dp[cur] == 1:
                break
            nxt = None
            for j in range(cur - 1, -1, -1):
                self.rebuild_comparisons += 1
                if dp[j] == dp[cur] - 1:
                    if mode == "strict":
                        ok = vals[j] < vals[cur]
                    else:
                        ok = vals[j] <= vals[cur]
                    if ok:
                        nxt = j
                        break
            cur = nxt
        order.reverse()
        return (order, [vals[i] for i in order])
