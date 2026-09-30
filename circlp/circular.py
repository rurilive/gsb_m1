"""circlp.circular: 环形序列最优化工具（当前为改造前基线）。

本模块以环形序列 values 为底座，首尾相邻，凡涉及相邻约束都要把首尾当成邻居。
当前实现全部是朴素枚举：

  - 不相邻选取最大和：枚举断点把环拆成链，再对每条链做指数级子集枚举；
  - 环形最大子段和：枚举断点拆环后对每条链平方级枚举全部子段；
  - 指定段数的最优划分：枚举断点拆环后对每条链枚举全部断点组合；
  - 最优选取方案（下标集合）、环相邻差最大和、最小不相邻删除代价。

这些做法直观，结果也对，可长度一多就露怯，枚举量随长度呈指数增长。另给两条
独立慢速做法用于与新路逐项对照：independent_split 按必不选首与必不选尾两侧
分别线性递推，independent_minus 用总和减去中间最小子段。非法长度、元素非数、
下标越界、段数与删除个数不合法都在入口拒绝。

全部只依赖标准库。
"""

import itertools


class Erro(Exception):
    """本包所有异常的根，上层只认这一个。"""


class ValueErro(Erro):
    """序列元素不是数值或序列形态不合法。"""


class IndexErro(Erro):
    """下标越界或下标集合不合法。"""


class ChooseErro(Erro):
    """段数或删除个数不合法。"""


# 指数级子集枚举允许的最长序列，超过即判为长度非法。
MAX_ENUM_LEN = 18


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _check_values(values):
    """把入参整理成数值元组，非序列或含非数一律报错。"""
    if isinstance(values, (str, bytes)):
        raise ValueErro("values 必须是数值序列")
    if not isinstance(values, (list, tuple)):
        raise ValueErro("values 必须是数值序列")
    out = []
    for value in values:
        if not _is_number(value):
            raise ValueErro("values 含非数值元素：%r" % (value,))
        out.append(value)
    return tuple(out)


class CircularOpt:
    """环形序列最优化工具（基线朴素版）。

    values 为环形序列，首尾相邻。所有公开方法在入口校验入参，非法即报错，
    绝不拖到递归半途才炸。朴素路径与独立慢速路径的枚举次数按调用前归零重算。
    """

    def __init__(self, values):
        self._values = _check_values(values)
        self._reset_counts()

    def _reset_counts(self):
        self.break_trials = 0
        self.linear_steps = 0
        self.minus_steps = 0

    @property
    def size(self):
        return len(self._values)

    @property
    def values(self):
        return list(self._values)

    def _require_enum_len(self):
        if len(self._values) > MAX_ENUM_LEN:
            raise ValueErro(
                "序列长度超过指数枚举上限 %d：%r" % (MAX_ENUM_LEN, len(self._values))
            )

    # -------------------------------------------------- 相邻选取最大和朴素

    def _chain_best_over_subsets(self, chain):
        """对一条链枚举全部子集，返回互不相邻子集的最大和，空取记零。"""
        n = len(chain)
        best = 0
        for mask in range(1 << n):
            self.break_trials += 1
            total = 0
            prev = -2
            ok = True
            for i in range(n):
                if (mask >> i) & 1:
                    if i == prev + 1:
                        ok = False
                        break
                    total += chain[i]
                    prev = i
            if ok and total > best:
                best = total
        return best

    def brute_max_sum(self):
        """不相邻选取的最大和（环形），枚举断点拆环再对每条链指数枚举。

        选了首就不能选尾。空环取零，单元素与两元素按退化情形处理，全负时允许
        空取，结果不为负。
        """
        self._reset_counts()
        self._require_enum_len()
        n = len(self._values)
        if n == 0:
            return 0
        if n == 1:
            return max(0, self._values[0])
        if n == 2:
            return max(0, self._values[0], self._values[1])
        best = 0
        for cut in range(n):
            chain = self._values[cut:] + self._values[:cut]
            head = self._chain_best_over_subsets(chain[:-1])
            tail = self._chain_best_over_subsets(chain[1:])
            if head > best:
                best = head
            if tail > best:
                best = tail
        return best

    # ------------------------------------------------------ 环形最大子段和

    def brute_max_segment(self):
        """环形最大子段和，枚举断点拆环后平方枚举全部连续子段。

        子段可以跨界，故对每个断点把环展成链再枚举全部连续子段取最大。空环与
        全负取零，即允许取空子段。
        """
        self._reset_counts()
        self._require_enum_len()
        n = len(self._values)
        if n == 0:
            return 0
        best = 0
        for cut in range(n):
            chain = self._values[cut:] + self._values[:cut]
            for start in range(n):
                total = 0
                for end in range(start, n):
                    total += chain[end]
                    self.break_trials += 1
                    if total > best:
                        best = total
        return best

    # ------------------------------------------------------------ 最优划分

    def brute_best_partition(self, parts):
        """把环划成 parts 个连续非空段，求各段和最大值的最小可能值。

        枚举断点拆环后枚举全部断点组合。parts 必须是 1 到长度之间的整数。
        """
        self._reset_counts()
        self._require_enum_len()
        n = len(self._values)
        if not _is_int(parts) or parts < 1 or parts > n:
            raise ChooseErro("parts 必须是 1 到长度之间的整数：%r" % (parts,))
        best = None
        for cut in range(n):
            chain = self._values[cut:] + self._values[:cut]
            for breaks in itertools.combinations(range(n - 1), parts - 1):
                self.break_trials += 1
                cutset = set(breaks)
                total = None
                segment = 0
                for i in range(n):
                    segment += chain[i]
                    if i in cutset:
                        if total is None or segment > total:
                            total = segment
                        segment = 0
                if total is None or segment > total:
                    total = segment
                if best is None or total < best:
                    best = total
        return best

    # ------------------------------------------------------ 环相邻差最大和

    def brute_diff_sum(self):
        """环形上相邻差最大和，分子集指数枚举。

        口径：在每个位置 i 取右邻减左邻（右邻为下一个下标，左邻为上一个下标，
        首尾相接）。求一个互不相邻且不选满首尾的下标集合，使按此口径累计的差
        最大。空环与单元素退化为零，结果不为负。
        """
        self._reset_counts()
        self._require_enum_len()
        n = len(self._values)
        if n <= 1:
            return 0
        coeff = []
        for i in range(n):
            right = self._values[(i + 1) % n]
            left = self._values[(i - 1) % n]
            coeff.append(right - left)
        best = 0
        for mask in range(1 << n):
            self.break_trials += 1
            total = 0
            prev = -2
            ok = True
            for i in range(n):
                if (mask >> i) & 1:
                    if i == prev + 1:
                        ok = False
                        break
                    total += coeff[i]
                    prev = i
            if ok and n > 2 and (mask & 1) and ((mask >> (n - 1)) & 1):
                ok = False
            if ok and total > best:
                best = total
        return best

    # ------------------------------------------------ 最小不相邻删除代价

    def brute_min_delete(self, count):
        """在环上删除恰好 count 个互不相邻的元素，求被删元素之和的最小值。

        count 必须是 0 到长度一半之间的整数，否则报错。逐个位置取可删下标组合
        后累计代价。空环只允许 count 为零。
        """
        self._reset_counts()
        self._require_enum_len()
        n = len(self._values)
        if not _is_int(count) or count < 0 or count > n // 2:
            raise ChooseErro("count 必须是 0 到长度一半之间的整数：%r" % (count,))
        if count == 0:
            return 0
        best = None
        for mask in range(1 << n):
            self.break_trials += 1
            bits = [i for i in range(n) if (mask >> i) & 1]
            if len(bits) != count:
                continue
            if any(b == a + 1 for a, b in zip(bits, bits[1:])):
                continue
            if n > 2 and bits[0] == 0 and bits[-1] == n - 1:
                continue
            total = 0
            for i in bits:
                total += self._values[i]
            if best is None or total < best:
                best = total
        return best

    # -------------------------------------------------------- 最优选取方案

    def brute_plan(self):
        """不相邻选取的最优方案，返回下标列表，并列时按下标序列字典序最小。

        与 brute_max_sum 同口径，取和最大者。空环返回空列表。选了首则不能选尾，
        全负时允许空取，返回空列表。
        """
        self._reset_counts()
        self._require_enum_len()
        n = len(self._values)
        best = []
        best_sum = 0
        for mask in range(1 << n):
            self.break_trials += 1
            picks = [i for i in range(n) if (mask >> i) & 1]
            if not self._valid_pick(picks, n):
                continue
            total = 0
            for i in picks:
                total += self._values[i]
            if total > best_sum:
                best = picks
                best_sum = total
            elif total == best_sum and tuple(picks) < tuple(best):
                best = picks
        return list(best)

    def _valid_pick(self, picks, n):
        for a, b in zip(picks, picks[1:]):
            if b == a + 1:
                return False
        if n > 2 and picks and picks[0] == 0 and picks[-1] == n - 1:
            return False
        return True

    # --------------------------------------------- 独立做法一：两侧线性递推

    def independent_split(self):
        """独立做法：必不选首与必不选尾两条链各做线性递推，取较大者。

        与枚举断点拆环路逐项一致，但不许调用朴素路径。空环、单元素与两元素按
        退化情形处理。
        """
        self._reset_counts()
        n = len(self._values)
        if n == 0:
            return 0
        if n == 1:
            return max(0, self._values[0])
        if n == 2:
            return max(0, self._values[0], self._values[1])
        head_chain = self._values[: n - 1]
        tail_chain = self._values[1:]
        head = self._linear(head_chain)
        tail = self._linear(tail_chain)
        return head if head > tail else tail

    def _linear(self, chain):
        """链上不相邻选取最大和，逐个推进线性递推，空取记零。"""
        prev2 = 0
        prev1 = 0
        for value in chain:
            self.linear_steps += 1
            take = prev2 + value
            if take < 0:
                take = 0
            cur = take if take > prev1 else prev1
            prev2 = prev1
            prev1 = cur
        return prev1

    # ----------------------------------- 独立做法二：总和减去中间最小子段

    def independent_minus(self):
        """独立做法：环形最大子段和用总和减去中间最小子段独立求。

        与枚举断点拆环路逐项一致，但不许调用朴素路径。全正的环整段最大取总和；
        全负或全零取零，即允许取空子段。空环取零。
        """
        self._reset_counts()
        n = len(self._values)
        if n == 0:
            return 0
        total = 0
        for value in self._values:
            total += value
        max_seg = self._linear_max()
        min_seg = self._linear_min()
        wrap = total - min_seg
        best = max_seg if max_seg > wrap else wrap
        if best < 0:
            best = 0
        return best

    def _linear_max(self):
        best = 0
        cur = 0
        for value in self._values:
            self.minus_steps += 1
            cur += value
            if cur < 0:
                cur = 0
            if cur > best:
                best = cur
        return best

    def _linear_min(self):
        best = 0
        cur = 0
        for value in self._values:
            self.minus_steps += 1
            cur += value
            if cur > 0:
                cur = 0
            if cur < best:
                best = cur
        return best

    # ------------------------------------------------------------ 计数与规模

    @property
    def break_trial_count(self):
        """最近一次朴素断点枚举的试探次数。"""
        return self.break_trials

    @property
    def linear_step_count(self):
        """最近一次独立两侧线性递推的转移次数。"""
        return self.linear_steps

    @property
    def minus_step_count(self):
        """最近一次独立总和减小段做法的转移次数。"""
        return self.minus_steps
