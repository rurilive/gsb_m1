"""取石子游戏的必胜判定与基本组合游戏的朴素实现（改造前基线）。

每一条能力都走同一类笨路：把局面直接展开成一棵走法树，对每个后继重新递归，
已经算过的局面再次遇到也照重算，不记忆化。具体包括：

  - single_win       单堆取石子游戏：一次可取走一至上限颗，递归枚举全部走法
                     判先手赢输。
  - single_min_takes 单堆取胜最少步数：在对手尽力拖延的前提下，先手把对方逼到
                     无路可走所需的最少落子步数，同样靠递归枚举。
  - multi_xor        多堆取石子游戏：把各堆石子数按位异或，非零则先手必胜。
  - multi_winning_move 多堆的一条制胜走法：按堆号与取走数从小到大试走，取第一
                     条把异或变成零的走法。
  - grundy           单个子游戏的格林数：把子游戏描述成一枚枚棋子的走法函数，
                     取后继格林数集合的最小不出现非负整数。
  - sum_win          多个独立子游戏之和：把各子游戏的状态整体拼接成一个局面后
                     递归枚举判赢输，不用格林数异或。

另有威索夫博弈（wythoff_win / wythoff_move）与斐波那契博弈（fib_win /
fib_move），同样靠递归枚举全部走法判赢输并给出确定口径的一条制胜走法。

这些做法直观可靠，结果一眼能看穿；堆数一多或单堆一大就指数级地重复展开。
本文件是改造前的基线，朴素路径在改造之后不得删除，新实现必须与它对同一批数据
给出的事实逐项对齐。

异常统一继承一个 Erro 基类：ParamErro / RuleErro / StateErro。
"""


class Erro(Exception):
    """取石子游戏工具包所有异常的基类，非法输入一律快速失败。"""


class ParamErro(Erro):
    """参数非法：类型不符、为负数、越出取值上限等。"""


class RuleErro(Erro):
    """规则非法：取法列表为空、含非正取走数、上限为负等。"""


class StateErro(Erro):
    """局面非法：与所声明的规则或规模不匹配。"""


def _as_nonneg_int(value, where):
    """把入参规整成非负整数，非法即抛 ParamErro。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ParamErro("%s 必须是非负整数，收到 %r" % (where, value))
    if value < 0:
        raise ParamErro("%s 必须是非负整数，收到 %r" % (where, value))
    return value


def _as_positive_int(value, where):
    """把入参规整成正整数，非法即抛 ParamErro。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ParamErro("%s 必须是正整数，收到 %r" % (where, value))
    if value < 1:
        raise ParamErro("%s 必须是正整数，收到 %r" % (where, value))
    return value


def _normalize_takes(takes):
    """把取法列表规整成升序去重的元组，非法即抛 RuleErro。"""
    try:
        items = list(takes)
    except TypeError:
        raise RuleErro("取法列表必须可迭代，收到 %r" % (takes,))
    if not items:
        raise RuleErro("取法列表不能为空")
    out = []
    for t in items:
        if isinstance(t, bool) or not isinstance(t, int):
            raise RuleErro("取走数必须是正整数，收到 %r" % (t,))
        if t < 1:
            raise RuleErro("取走数必须是正整数，收到 %r" % (t,))
        out.append(t)
    return tuple(sorted(set(out)))


class NimGar:
    """取石子游戏的朴素求解器（改造前基线）。

    每次调用都只由入参决定结果，调用前把上一次的展开计数归零后重新累加；实例
    本身不保存任何跨调用的派生结论。同一批输入连续调用两次，结果与计数都应逐位
    一致。
    """

    def __init__(self):
        # 本次调用朴素递归实际重入局面的次数，每次进入入口前归零后重新累加。
        self.expansions = 0

    # ----------------------------------------------------------------
    # 单堆取石子游戏：对每个后继重新递归
    # ----------------------------------------------------------------
    def single_win(self, size, max_take=1, takes=None):
        """单堆先手是否必胜。

        size 是石子数（非负整数），初始局面大小为 size。取法默认是一次可取走
        一至 max_take 颗，给出 takes 时按 takes 里的取走数取（正整数且不超过
        size 的才合法）。出度为空的局面必败。递归枚举全部走法判赢输。
        """
        size = _as_nonneg_int(size, "石子数")
        moves = self._single_moves(size, max_take, takes)
        self.expansions = 0
        return self._rec_single(size, moves)

    def _single_moves(self, size, max_take, takes):
        """把单堆的取法规整成一份可复用的取走数元组。"""
        if takes is None:
            max_take = _as_positive_int(max_take, "单次最多取走数")
            return tuple(range(1, max_take + 1))
        return _normalize_takes(takes)

    def _rec_single(self, n, moves):
        """朴素递归求单堆赢输：每个后继都从头再算一遍，不记忆化。"""
        self.expansions += 1
        for take in moves:
            if take > n:
                continue
            if not self._rec_single(n - take, moves):
                return True
        return False

    # ----------------------------------------------------------------
    # 单堆取胜最少步数：在必败后继里挑自己后续步数最少者
    # ----------------------------------------------------------------
    def single_min_takes(self, size, max_take=1, takes=None):
        """先手必胜时把对方逼到无路可走所需的最少落子步数，必败返回 None。

        size 是石子数（非负整数）。步数按先手自己落子次数计；对手每一步都尽力
        拖延，先手在必胜的前提下每一步都尽快取胜。递归枚举全部走法，先算出整局
        双方合计的落子数，再由先手落子在先换算成先手自己的步数。必胜局面无解时
        返回 None。
        """
        size = _as_nonneg_int(size, "石子数")
        moves = self._single_moves(size, max_take, takes)
        self.expansions = 0
        if not self._rec_single(size, moves):
            return None
        total = self._rec_single_min(size, moves)
        return (total + 1) // 2

    def _rec_single_min(self, n, moves):
        """朴素递归求整局合计落子数：必胜取最短，必败尽力拖延。"""
        self.expansions += 1
        legal = [take for take in moves if take <= n]
        if not legal:
            return 0
        if self._rec_single(n, moves):
            best = None
            for take in legal:
                if not self._rec_single(n - take, moves):
                    cur = self._rec_single_min(n - take, moves) + 1
                    if best is None or cur < best:
                        best = cur
            return best
        worst = 0
        for take in legal:
            cur = self._rec_single_min(n - take, moves) + 1
            if cur > worst:
                worst = cur
        return worst

    # ----------------------------------------------------------------
    # 多堆取石子游戏：各堆石子数按位异或
    # ----------------------------------------------------------------
    def multi_xor(self, heaps):
        """多堆石子游戏各堆数的按位异或。

        heaps 是非负整数序列，每堆石子数；空序列的异或为零。异或非零则先手
        必胜，为零则先手必败。
        """
        self.expansions = 0
        total = 0
        for h in heaps:
            total ^= _as_nonneg_int(h, "堆石子数")
        return total

    def multi_winning_move(self, heaps):
        """多堆的一条制胜走法，没有则返回 None。

        按堆号从小到大、同一堆内取走数从小到大试走，返回第一条把异或变成零的
        走法，形如（堆号, 取走数）。堆号从零计。异或为零时无制胜走法，返回
        None。返回的走法取走后必须落在合法局面上。
        """
        values = [_as_nonneg_int(h, "堆石子数") for h in heaps]
        self.expansions = 0
        total = 0
        for v in values:
            total ^= v
        if total == 0:
            return None
        for i, v in enumerate(values):
            target = v ^ total
            if target < v:
                return (i, v - target)
        return None

    # ----------------------------------------------------------------
    # 格林数：后继格林数集合的最小不出现非负整数
    # ----------------------------------------------------------------
    def grundy(self, start, move_fn):
        """单个子游戏起点局面的格林数，每个后继都从头再递归。

        start 是子游戏的状态（非负整数），move_fn(state) 返回该状态的全部后继
        （非负整数序列）。出度为空的局面格林数为零。状态非法抛 StateErro。
        """
        start = _as_nonneg_int(start, "子游戏状态")
        self.expansions = 0
        return self._rec_grundy(start, move_fn)

    def _rec_grundy(self, state, move_fn):
        """朴素递归求格林数，不记忆化。"""
        self.expansions += 1
        self._check_state(state)
        succ = self._successors(state, move_fn)
        if not succ:
            return 0
        seen = set()
        for s in succ:
            seen.add(self._rec_grundy(s, move_fn))
        mex = 0
        while mex in seen:
            mex += 1
        return mex

    def _check_state(self, state):
        """校验子游戏状态是非负整数，非法即抛 StateErro。"""
        if isinstance(state, bool) or not isinstance(state, int) or state < 0:
            raise StateErro("子游戏状态必须是非负整数，收到 %r" % (state,))
        return state

    def _successors(self, state, move_fn):
        """调用走法函数取后继并逐个规整成非负整数。"""
        if not callable(move_fn):
            raise StateErro("走法必须是可调用对象，收到 %r" % (type(move_fn).__name__,))
        try:
            raw = list(move_fn(state))
        except Erro:
            raise
        except TypeError:
            raise StateErro("走法返回值必须可迭代，状态 %r" % (state,))
        return tuple(_as_nonneg_int(s, "后继状态") for s in raw)

    # ----------------------------------------------------------------
    # 多个独立子游戏之和：把状态整体拼接后递归
    # ----------------------------------------------------------------
    def sum_win(self, starts, move_fns):
        """多个独立子游戏之和先手是否必胜。

        starts 是各子游戏的起始状态序列，move_fns 是与之一一对应的走法函数
        序列，每个子游戏互相独立。判赢输时把各子游戏的状态整体拼接成一个局面，
        轮到谁走谁就挑一个子游戏走它的一步，递归枚举全部走法，不用格林数异或。
        空序列视同没有走法的必败局面。
        """
        states = tuple(self._check_state(s) for s in starts)
        fns = tuple(move_fns)
        if len(fns) != len(states):
            raise StateErro("走法序列与起始状态序列长度不一致")
        self.expansions = 0
        return self._rec_sum(states, fns)

    def _rec_sum(self, states, fns):
        """朴素递归：把拼接局面整体展开，对每个后继重新递归。"""
        self.expansions += 1
        for i, state in enumerate(states):
            for nxt in self._successors(state, fns[i]):
                moved = states[:i] + (nxt,) + states[i + 1:]
                if not self._rec_sum(moved, fns):
                    return True
        return False

    # ----------------------------------------------------------------
    # 威索夫博弈：从一堆取任意颗，或从两堆取同样多颗
    # ----------------------------------------------------------------
    def wythoff_win(self, a, b):
        """威索夫博弈先手是否必胜。

        两堆石子数 a 与 b（非负整数）。一次可行走法有两条：从任意一堆取走任意
        正整数颗，或从两堆各取走同样多颗（正整数）。递归枚举全部走法判赢输。
        """
        a = _as_nonneg_int(a, "第一堆石子数")
        b = _as_nonneg_int(b, "第二堆石子数")
        self.expansions = 0
        return self._rec_wythoff(a, b)

    def _rec_wythoff(self, a, b):
        """朴素递归求威索夫局面赢输，每个后继都重算。"""
        self.expansions += 1
        if a == 0 and b == 0:
            return False
        for take in range(1, a + 1):
            if not self._rec_wythoff(a - take, b):
                return True
        for take in range(1, b + 1):
            if not self._rec_wythoff(a, b - take):
                return True
        m = min(a, b)
        for take in range(1, m + 1):
            if not self._rec_wythoff(a - take, b - take):
                return True
        return False

    def wythoff_move(self, a, b):
        """威索夫博弈的一条制胜走法，没有则返回 None。

        按确定口径给出：先试从第二堆取（堆号一），再试从第一堆取（堆号零），
        最后试从两堆同取，每种情形取走数从小到大，返回第一条走到必败局面的
        走法。走法形如（堆号, 取走数），从两堆同取时堆号为负一。
        """
        a = _as_nonneg_int(a, "第一堆石子数")
        b = _as_nonneg_int(b, "第二堆石子数")
        self.expansions = 0
        if not self._rec_wythoff(a, b):
            return None
        for take in range(1, b + 1):
            if not self._rec_wythoff(a, b - take):
                return (1, take)
        for take in range(1, a + 1):
            if not self._rec_wythoff(a - take, b):
                return (0, take)
        m = min(a, b)
        for take in range(1, m + 1):
            if not self._rec_wythoff(a - take, b - take):
                return (-1, take)
        return None

    # ----------------------------------------------------------------
    # 斐波那契博弈：取走数不超过上一手的两倍
    # ----------------------------------------------------------------
    def fib_win(self, n):
        """斐波那契博弈先手是否必胜。

        n 是石子数（非负整数），两方轮流取石子：先手首手可取一至 n 减一颗（必须
        留下至少一颗）；此后每手取走的石子数不超过上一手的两倍。取走最后一颗者
        胜。递归枚举全部走法。先手必败的局面恰好是石子数取斐波那契数时。
        """
        n = _as_nonneg_int(n, "石子数")
        self.expansions = 0
        return self._rec_fib(n, n, True)

    def _rec_fib(self, remaining, previous, is_first):
        """朴素递归：remaining 是剩余石子数，previous 是上一手取走数，is_first 标记先手首手。"""
        self.expansions += 1
        if remaining == 0:
            return False
        if is_first:
            limit = remaining - 1
        else:
            limit = min(2 * previous, remaining)
        for take in range(1, limit + 1):
            if not self._rec_fib(remaining - take, take, False):
                return True
        return False

    def fib_move(self, n):
        """斐波那契博弈的一条制胜走法，没有则返回 None。

        按确定口径给出：返回先手应取走的石子数，取走数从小到大取第一条能走到
        必败局面的走法。先手必败时返回 None。
        """
        n = _as_nonneg_int(n, "石子数")
        self.expansions = 0
        if not self._rec_fib(n, n, True):
            return None
        for take in range(1, n):
            if not self._rec_fib(n - take, take, False):
                return take
        return None
