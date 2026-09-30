"""约瑟夫环淘汰过程的朴素模拟实现。

这一版只做最直白的事：把剩下的人装进一个列表当圆圈，反复做切片与旋转，
每淘汰一人就把列表当作队列整体搬家一次，并且重新从头逐个数 k 个。结果全对，
但每次淘汰都是线性搬家，整轮下来是平方量级，规模一大就慢。
"""


class JosephusError(Exception):
    """本模块所有异常的基类。"""


class InvalidCountError(JosephusError):
    """人数或步长不满足约束。"""


class PositionError(JosephusError):
    """淘汰次序越界。"""


class StartConventionError(JosephusError):
    """起始编号口径不是约定的两种之一。"""


# 起始编号口径：zero 表示从零开始编号，one 表示从一开始编号。
_ZERO = "zero"
_ONE = "one"


def _as_int(value, name):
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidCountError("%s 必须是整数" % name)
    return value


def _check_n(n):
    _as_int(n, "人数")
    if n < 0:
        raise InvalidCountError("人数不能为负")
    return n


def _check_k(k):
    _as_int(k, "步长")
    if k < 1:
        raise InvalidCountError("步长必须为正")
    return k


def _check_convention(convention):
    if convention not in (_ZERO, _ONE):
        raise StartConventionError("起始编号口径只能是 zero 或 one")
    return convention


def _initial(n, convention):
    # 从左到右是圆圈上的顺序，编号相邻的人挨在一起。
    if convention == _ONE:
        return list(range(1, n + 1))
    return list(range(0, n))


class Josephus:
    """拦圈淘汰过程的朴素模拟器。

    约定：从圆圈起点开始数 k 个人，数到第 k 个就淘汰；被淘汰者的下一个人
    接着作为新的起点，若人已走完一圈则回绕到仍剩下的人。球步长为 k。
    """

    def __init__(self, n, k, start=0, convention=_ZERO):
        _check_n(n)
        _check_k(k)
        _check_convention(convention)
        # 起点只是用来定位第一次从哪里开始数，落到圆圈内。
        _as_int(start, "起点")
        self.n = n
        self.k = k
        self.start = start
        self.convention = convention
        self._moves = 0
        self._added = 0

    # --- 朴素模拟：反复切片与旋转，淘汰一人就整体搬一次家 ---

    def _play(self):
        """跑完整轮朴素模拟。

        返回 (淘汰序列, 每次淘汰时已走过的搬家步数, 结束时搬家总步数)。
        """
        people = _initial(self.n, self.convention)
        if not people:
            self._added = 0
            return [], [], 0

        # 把圆圈旋转到起点位置；start 是相对编号的位移，先折算成下标。
        base = _initial(self.n, self.convention)
        if self.start in base:
            pos = base.index(self.start)
        else:
            pos = 0
        people = people[pos:] + people[:pos]
        # 旋转本身也算搬家，如实计数。
        self._moves += pos

        eliminated = []
        moves_snapshot = []
        while people:
            # 朴素数法：从当前位置开始，逐个数 k 个，每一步就往前挪一格。
            index = 0
            for _ in range(self.k - 1):
                index += 1
                if index >= len(people):
                    index = 0
            # 把数过的人整体搬家到队尾，让被淘汰者站到队首。
            moved = people[index:] + people[:index]
            self._moves += len(moved)
            victim = moved[0]
            eliminated.append(victim)
            moves_snapshot.append(self._moves)
            rest = moved[1:]
            # 剩下的整体接在被淘汰者后面，维持圆圈顺序（这里也算一次搬家）。
            self._moves += len(rest)
            people = rest
        total = self._moves
        self._added = total
        return eliminated, moves_snapshot, total

    def survivor(self):
        """最后幸存者的编号；人数为零时没有幸存者，抛异常。"""
        if self.n == 0:
            raise InvalidCountError("人数为零时没有幸存者")
        sequence, _, _ = self._play()
        return sequence[-1]

    def order(self):
        """完整淘汰序列，序号从 1 起。"""
        sequence, _, _ = self._play()
        return sequence

    def rank_to_be_removed(self, m):
        """第 m 个被淘汰者的编号，m 从 1 起。"""
        _as_int(m, "次序")
        sequence, _, _ = self._play()
        if m < 1 or m > len(sequence):
            raise PositionError("淘汰次序越界")
        return sequence[m - 1]

    def elimination_index(self, value):
        """某个编号是在第几个被淘汰的，从 1 起；幸存者不在淘汰序列里则抛异常。"""
        sequence, _, _ = self._play()
        if value not in sequence:
            raise PositionError("编号不在淘汰序列中")
        return sequence.index(value) + 1

    # --- 规模对照：暴露朴素路径走了多少步搬家 ---

    def move_count(self):
        """跑一遍朴素模拟并返回总的搬家步数。"""
        self._play()
        return self._added

    def move_counts_per_step(self):
        """每次淘汰后累计的搬家步数序列，用来观察平方量级的增长。"""
        _, snapshot, _ = self._play()
        return snapshot

    def replay_order(self):
        """重跑一遍模拟，返回淘汰序列；用于验证固定输入重复跑结果一致。"""
        sequence, _, _ = self._play()
        return list(sequence)


class BatchFacts:
    """对一批参数批量求出各项事实，方便调用方一次性取结果。"""

    def __init__(self, params):
        self.params = list(params)

    def run(self):
        facts = []
        for n, k in self.params:
            sim = Josephus(n, k)
            sequence = sim.order()
            facts.append(
                {
                    "n": n,
                    "k": k,
                    "survivor": sequence[-1] if sequence else None,
                    "order": sequence,
                    "moves": sim.move_count(),
                }
            )
        return facts
