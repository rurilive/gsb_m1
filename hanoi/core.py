"""汉诺塔递归结构工具的朴素实现（改造前基线）。

内部只有一条路：递归生成完整的移动序列，再在序列上做各种统计与校验。
盘数一大，移动序列长度按二的 n 次方减一增长，时间与内存都被拖垮；三柱、
四柱、以及不能从某柱直接到某柱的变体各自单写一份，彼此不共用口径。

纯标准库，无外部依赖。
"""


class HanoiError(Exception):
    """本包所有错误的共同基类。"""

    pass


class InvalidPegError(HanoiError):
    """柱编号不在允许范围内。"""

    pass


class InvalidMoveError(HanoiError):
    """移动序列里出现不合法的一步，或者序列长度对不上。"""

    pass


class StepOutOfRangeError(HanoiError):
    """第 k 步越界。"""

    pass


def _check_n(n):
    """把盘数挡在最前面：必须是整数，且不小于零。"""
    if isinstance(n, bool) or not isinstance(n, int):
        raise HanoiError("盘数必须是整数")
    if n < 0:
        raise HanoiError("盘数不能为负")
    return n


def _check_k(k):
    """步号必须是整数。"""
    if isinstance(k, bool) or not isinstance(k, int):
        raise HanoiError("步号必须是整数")
    return k


def _check_peg(peg, allowed=(0, 1, 2)):
    """柱编号必须是允许集合里的整数。"""
    if isinstance(peg, bool) or not isinstance(peg, int):
        raise InvalidPegError("柱编号必须是整数")
    if peg not in allowed:
        raise InvalidPegError("柱编号非法")


def move_count(n):
    """n 层汉诺塔的最少移动步数，用最简单的循环从零累加。"""
    _check_n(n)
    total = 0
    for _ in range(n):
        total = total * 2 + 1
    return total


def _generate(n, src, dst, aux, moves):
    """递归地把 n 个盘从 src 搬到 dst：先搬上面的 n-1 到 aux，再搬最大盘，
    最后把 aux 上的 n-1 搬到 dst。每搬一个盘就往 moves 里追加一步。"""
    if n == 0:
        return
    _generate(n - 1, src, aux, dst, moves)
    moves.append((n, src, dst))
    _generate(n - 1, aux, dst, src, moves)


def generate_moves(n, src=0, dst=2, aux=1):
    """生成完整移动序列，每一步是 (盘号, 起始柱, 目标柱)。"""
    _check_n(n)
    moves = []
    _generate(n, src, dst, aux, moves)
    return moves


def step_moves(n):
    """把完整序列切成单步的二元组 (起始柱, 目标柱)。"""
    _check_n(n)
    return [(src, dst) for _disk, src, dst in generate_moves(n)]


def min_moves_to(n, target):
    """把整座塔搬到指定柱的最少步数，先递归生成序列再取长度。"""
    _check_n(n)
    _check_peg(target)
    if n == 0:
        return 0
    if target == 2:
        return len(generate_moves(n))
    return len(generate_moves(n, 0, target, 3 - target))


def kth_move(n, k):
    """第 k 步移动了哪个盘、从哪到哪，k 从零开始，先造出整个序列再取第 k 项。"""
    _check_n(n)
    _check_k(k)
    moves = generate_moves(n)
    if k < 0 or k >= len(moves):
        raise StepOutOfRangeError("步号越界")
    return moves[k]


def is_valid_sequence(n, moves):
    """逐步重放给定序列，判断它是否是搬完 n 个盘的合法走法。"""
    _check_n(n)
    try:
        steps = list(moves)
    except TypeError:
        raise InvalidMoveError("移动序列必须可迭代")
    for step in steps:
        if not isinstance(step, tuple) or len(step) != 2:
            raise InvalidMoveError("每一步必须是二元组")
        src, dst = step
        _check_peg(src)
        _check_peg(dst)
    if len(steps) != move_count(n):
        return False
    pegs = [list(range(n, 0, -1)), [], []]
    for src, dst in steps:
        if not pegs[src]:
            return False
        if pegs[dst] and pegs[dst][-1] < pegs[src][-1]:
            return False
        pegs[dst].append(pegs[src].pop())
    return pegs[2] == list(range(n, 0, -1))


def hanoi4(n):
    """四柱汉诺塔的最少步数，用经典递推逐层试 k 取最小，索引从零开始。"""
    _check_n(n)
    if n == 0:
        return 0
    table = [0]
    for m in range(1, n + 1):
        best = None
        for k in range(m):
            cost = 2 * table[k] + (1 << (m - k)) - 1
            if best is None or cost < best:
                best = cost
        table.append(best)
    return table[n]


def _restricted_neighbors(state, forbidden):
    """列出某状态下所有合法后继状态。"""
    result = []
    for src in range(3):
        if not state[src]:
            continue
        disk = state[src][-1]
        for dst in range(3):
            if src == dst or (src, dst) in forbidden:
                continue
            if state[dst] and state[dst][-1] < disk:
                continue
            nxt = list(state)
            nxt[src] = nxt[src][:-1]
            nxt[dst] = nxt[dst] + (disk,)
            result.append(tuple(nxt))
    return result


def min_moves_restricted(n):
    """限定规则变体：三柱，但两端的柱之间不能直接对搬，必须经中间柱中转。
    朴素做法把状态逐层展开，用最直白的最短路径搜索求最少步数。"""
    _check_n(n)
    if n == 0:
        return 0
    forbidden = {(0, 2), (2, 0)}
    start = (tuple(range(n, 0, -1)), (), ())
    goal = ((), (), tuple(range(n, 0, -1)))
    dist = {start: 0}
    pending = [start]
    while pending:
        best_state = None
        best_cost = None
        for state in pending:
            cost = dist[state]
            if best_cost is None or cost < best_cost:
                best_cost = cost
                best_state = state
        pending.remove(best_state)
        if best_state == goal:
            return best_cost
        for nxt in _restricted_neighbors(best_state, forbidden):
            cost = best_cost + 1
            if nxt not in dist or cost < dist[nxt]:
                dist[nxt] = cost
                if nxt not in pending:
                    pending.append(nxt)
    return dist[goal]
