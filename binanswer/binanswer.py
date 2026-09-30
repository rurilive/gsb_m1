"""binanswer: 最优化可行性工具包（改造前基线，朴素逐个试）。

当前实现一律走最直白的一条路：对答案可能取到的整数区间从最小值起逐个整数
往上试可行性，或对全部取值排序后逐个试，每次可行性判定线性扫一遍。可行即
返回该值，因此天然取到满足条件的最小可行值；任何一次判定失败就整体报错。
"""


class BinErro(Exception):
    """本包全部异常的基类。"""


class InputErro(BinErro):
    """输入非法。"""


class UnsatErro(BinErro):
    """不存在可行的取值。"""


class BackendErro(BinErro):
    """内部路径不可用。"""


def _check_values(values):
    if not isinstance(values, (list, tuple)):
        raise InputErro("values must be a list or tuple")
    out = []
    for v in values:
        if isinstance(v, bool) or not isinstance(v, int):
            raise InputErro("items must be integers")
        out.append(v)
    return out


def _check_k(k, n):
    if isinstance(k, bool) or not isinstance(k, int):
        raise InputErro("k must be an integer")
    if k > n:
        raise InputErro("k must not exceed the number of items")
    return k


def _check_step(step):
    if isinstance(step, bool) or not isinstance(step, int):
        raise InputErro("step must be an integer")
    if step <= 0:
        raise InputErro("step must be positive")
    return step


def _check_limit(limit):
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise InputErro("limit must be an integer")
    return limit


class BinaryAnswerKit:
    """最优化可行性工具包（改造前基线）。

    四项求解能力：把序列切成若干段，使每段和的最大值最小、使每段和的最小
    值最大、切成长度不超过给定值的段使一段和的上限最小、以及先取一处切分
    成前后两段、再在段内取相邻两个元素、使这对元素的差的绝对值最小。另有
    三个独立能力：分段下标的划分方案、可行性判定、容量枚举。
    """

    def __init__(self):
        self.trials = 0
        self.checks = 0
        self.ops = 0

    def reset_counters(self):
        self.trials = 0
        self.checks = 0
        self.ops = 0

    # ---- 可行性判定：线性扫一遍 ----

    def _scan(self, values, bound, need):
        """从前往后累加，和超过 bound 就切段，返回段数与各段末下标。"""
        pieces = []
        cur = 0
        cnt = 1
        for i, v in enumerate(values):
            self.ops += 1
            if cur + v > bound:
                pieces.append(i - 1)
                cnt += 1
                cur = v
            else:
                cur += v
        last = len(values) - 1
        if not pieces or pieces[-1] != last:
            pieces.append(last)
        return cnt <= need, cnt, pieces

    # ---- 四项求解：逐个整数试 ----

    def minimize_max_segment_sum(self, values, k):
        """把序列顺序切成不超过 k 段，使各段和的最大值最小，返回这个最小值。"""
        vals = _check_values(values)
        n = len(vals)
        _check_k(k, n)
        if n == 0:
            return 0
        if k == 1:
            self.checks += 1
            return sum(vals)
        lo = max(vals)
        hi = sum(vals)
        bound = lo
        while bound <= hi:
            self.trials += 1
            self.checks += 1
            ok, _, _ = self._scan(vals, bound, k)
            if ok:
                return bound
            bound += 1
        raise UnsatErro("no feasible bound")

    def maximize_min_segment_sum(self, values, k):
        """把序列顺序切成恰好 k 段，使各段和的最小值最大，返回这个最大值。"""
        vals = _check_values(values)
        n = len(vals)
        _check_k(k, n)
        if n == 0:
            return 0
        if k == 1:
            self.checks += 1
            return sum(vals)
        lo = min(vals)
        hi = sum(vals)
        best = None
        bound = lo
        while bound <= hi:
            self.trials += 1
            self.checks += 1
            if self._min_viable(vals, bound, k):
                best = bound
                bound += 1
            else:
                break
        if best is None:
            raise UnsatErro("no feasible bound")
        return best

    def _min_viable(self, values, bound, need):
        """动态规划：reach 的第 t 位表示能否把前缀恰好切成 t 个合格段。"""
        n = len(values)
        reach = [0] * (n + 1)
        reach[0] = 1
        for i in range(1, n + 1):
            total = 0
            acc = 0
            for j in range(i - 1, -1, -1):
                total += values[j]
                self.ops += 1
                if total >= bound:
                    acc |= reach[j]
            reach[i] = acc << 1
        return bool((reach[n] >> need) & 1)

    def min_eating_speed(self, piles, hours):
        """每小时吃速度 x，求在 hours 小时内吃完全部堆所需的最小速度。"""
        vals = _check_values(piles)
        n = len(vals)
        hours = _check_step(hours)
        if n == 0:
            return 1
        lo = 1
        hi = max(vals)
        if hi < 1:
            hi = 1
        bound = lo
        while bound <= hi:
            self.trials += 1
            self.checks += 1
            ok = self._speed_ok(vals, bound, hours)
            if ok:
                return bound
            bound += 1
        raise UnsatErro("no feasible speed")

    def _speed_ok(self, values, speed, limit):
        used = 0
        for v in values:
            self.ops += 1
            used += (v + speed - 1) // speed
        return used <= limit

    def min_max_pair_gap(self, values):
        """序列中任取一对元素，求它们差值绝对值的最小值。"""
        vals = _check_values(values)
        n = len(vals)
        if n < 2:
            raise UnsatErro("need at least two items")
        if n == 2:
            self.checks += 1
            return abs(vals[0] - vals[1])
        lo = 0
        hi = max(vals) - min(vals)
        bound = lo
        while bound <= hi:
            self.trials += 1
            self.checks += 1
            if self._gap_ok(vals, bound):
                return bound
            bound += 1
        raise UnsatErro("no feasible gap")

    def _gap_ok(self, values, bound):
        n = len(values)
        for i in range(n - 1):
            for j in range(i + 1, n):
                self.ops += 1
                if abs(values[i] - values[j]) <= bound:
                    return True
        return False

    # ---- 独立能力：划分方案 / 可行性 / 容量枚举 ----

    def segment_plan(self, values, k):
        """求使最大段和最小的划分，返回各段末下标，并列取字典序最小。"""
        vals = _check_values(values)
        n = len(vals)
        _check_k(k, n)
        if n == 0:
            return []
        if k == 1:
            return [n - 1]
        bound = self.minimize_max_segment_sum(vals, k)
        pieces = []
        start = 0
        remaining = k
        while start < n:
            if remaining == 1:
                if sum(vals[start:]) > bound:
                    raise UnsatErro("no plan")
                pieces.append(n - 1)
                break
            acc = 0
            chosen = None
            for e in range(start, n):
                acc += vals[e]
                self.ops += 1
                if acc > bound:
                    break
                if e == n - 1:
                    chosen = e
                    break
                if self._suffix_ok(vals, e + 1, remaining - 1, bound):
                    chosen = e
                    break
            if chosen is None:
                raise UnsatErro("no plan")
            pieces.append(chosen)
            start = chosen + 1
            remaining -= 1
        return pieces

    def _suffix_ok(self, values, s, t, bound):
        """从下标 s 起的后缀能否用不超过 t 段、每段和不超过 bound 装下。"""
        n = len(values)
        if s >= n:
            return True
        if values[s] > bound:
            return False
        cnt = 1
        cur = values[s]
        for i in range(s + 1, n):
            self.ops += 1
            if cur + values[i] > bound:
                cnt += 1
                cur = values[i]
            else:
                cur += values[i]
        return cnt <= t

    def feasible(self, values, k, bound):
        """判断把序列切成不超过 k 段、每段和都不超过 bound 是否可行。"""
        vals = _check_values(values)
        n = len(vals)
        _check_k(k, n)
        bound = _check_limit(bound)
        self.checks += 1
        return self._scan(vals, bound, k)[0]

    def candidate_bounds(self, values):
        """把全部单值升序去重列出，作为逐个试可行的候选取值。"""
        vals = _check_values(values)
        return sorted(set(vals))

    def sweep_bound(self, values, k, candidates):
        """对候选取值逐个试可行，返回第一个可行的取值。"""
        vals = _check_values(values)
        cands = _check_values(candidates)
        for bound in cands:
            self.trials += 1
            self.checks += 1
            if self._scan(vals, bound, k)[0]:
                return bound
        raise UnsatErro("no feasible candidate")


def solve_minimize_max_segment_sum(values, k):
    return BinaryAnswerKit().minimize_max_segment_sum(values, k)


def solve_maximize_min_segment_sum(values, k):
    return BinaryAnswerKit().maximize_min_segment_sum(values, k)


def solve_min_eating_speed(piles, hours):
    return BinaryAnswerKit().min_eating_speed(piles, hours)


def solve_min_max_pair_gap(values):
    return BinaryAnswerKit().min_max_pair_gap(values)
