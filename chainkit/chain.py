"""chainkit：矩阵链最优加括号方案的朴素实现。

一条矩阵链是一串矩阵的维度，用一维整数序列 dims 表示：第 i 个矩阵的行数是
dims[i]，最后一个矩阵的列数是 dims[-1]。矩阵个数 n 等于 len(dims) 减一。相邻
矩阵要能按序相乘，须前一个的列数等于后一个的行数；用一维序列表示时这一条天然
成立，链本身保证可乘。

本模块当前一律用最直白的递归枚举：对每个区间枚举全部断开位置，左右两半各自
递归重算代价，取最小或最大者。方案也用同一套枚举回代拼出，并列时取断开位置
最小的那个。结果正确，但不同断开位置的子区间会被反复重算，链一长重复量爆炸，
量级随矩阵个数指数上涨。

退化规定：矩阵个数为零或一时没有断开位置，乘法次数为零，方案是个叶子下标，
括号串为空串或那一个下标。
"""


class ChainError(Exception):
    """chainkit 里所有可诊断错误的基类。

    message 是单行说明；position 是出错位置，取链上下标或括号串上下标；data 是
    出错时问题数据的人读摘要。上层按本基类统一捕获。
    """

    def __init__(self, message, position=0, data=""):
        super().__init__(message)
        self.message = message
        self.position = position
        self.data = data

    def __str__(self):
        return "%s (position %d)" % (self.message, self.position)


def check_dims(dims):
    """校验维度序列并返回矩阵个数。

    dims 必须是非空整数序列，每个数都得是正整数；负数或零会让某一步不可乘，
    一律抛 ChainError。序列长度小于二时无法确定矩阵个数，也抛 ChainError。
    布尔值按非整数看待。
    """
    dims = list(dims)
    if len(dims) < 2:
        raise ChainError("维度序列太短，无法确定矩阵个数", position=0, data=str(dims))
    for i, d in enumerate(dims):
        if not isinstance(d, int) or isinstance(d, bool):
            raise ChainError("维度必须是整数", position=i, data=str(d))
        if d <= 0:
            raise ChainError("维度必须为正", position=i, data=str(d))
    return len(dims) - 1


def is_feasible(dims):
    """判断一条链是否合法，合法返回真，非法返回假，绝不抛错。

    合法即长度至少为二、每个都是正整数。供上层先探再决定是否处理。
    """
    try:
        check_dims(dims)
        return True
    except ChainError:
        return False


def feasible(dims):
    """is_feasible 的别名，语义完全一致。"""
    return is_feasible(dims)


def _check_pair(n, i, j):
    """校验区间端点，左闭右闭，越界或左大于右抛 ChainError。"""
    for k in (i, j):
        if not isinstance(k, int) or isinstance(k, bool):
            raise ChainError("区间端点必须是整数", position=0, data=str(k))
    if i < 0 or i >= n or j < 0 or j >= n:
        raise ChainError("区间端点越界", position=i, data="")
    if j < i:
        raise ChainError("区间不合法", position=j, data="")


def _mul(dims, a, b, c):
    """三处相邻下标给出的乘法次数，取下标处的维度相乘。"""
    return dims[a] * dims[b] * dims[c]


def naive_cost(dims, i, j):
    """朴素求第 i 到第 j 个矩阵相乘的最少标量乘法次数。

    对每个断开位置 k 把区间切成左右两半，左右各自递归重算，取和加本次代价
    最小者。区间里只有一个矩阵时为零。
    """
    n = check_dims(dims)
    _check_pair(n, i, j)
    if i == j:
        return 0
    best = None
    for k in range(i, j):
        here = (naive_cost(dims, i, k) + naive_cost(dims, k + 1, j)
                + _mul(dims, i, k + 1, j + 1))
        if best is None or here < best:
            best = here
    return best


def naive_optimal(dims, i, j):
    """朴素求第 i 到第 j 个矩阵的最少次数与一个最优方案。

    方案是嵌套的二元组，叶子是矩阵下标。并列最优时取断开位置最小的那个，
    保证同一批输入下结果确定。
    """
    n = check_dims(dims)
    _check_pair(n, i, j)
    if i == j:
        return 0, i
    best = None
    split = None
    for k in range(i, j):
        here = (naive_cost(dims, i, k) + naive_cost(dims, k + 1, j)
                + _mul(dims, i, k + 1, j + 1))
        if best is None or here < best:
            best = here
            split = k
    left = naive_optimal(dims, i, split)[1]
    right = naive_optimal(dims, split + 1, j)[1]
    return best, (left, right)


def naive_max_cost(dims, i, j):
    """朴素求第 i 到第 j 个矩阵相乘的最大标量乘法次数。

    枚举方式与最少次数一致，只是取和最大者；区间只有一个矩阵时为零。
    """
    n = check_dims(dims)
    _check_pair(n, i, j)
    if i == j:
        return 0
    best = None
    for k in range(i, j):
        here = (naive_max_cost(dims, i, k) + naive_max_cost(dims, k + 1, j)
                + _mul(dims, i, k + 1, j + 1))
        if best is None or here > best:
            best = here
    return best


def naive_max_optimal(dims, i, j):
    """朴素求第 i 到第 j 个矩阵的最大次数与一个对应方案。

    并列最大时取断开位置最小的那个，保证确定。
    """
    n = check_dims(dims)
    _check_pair(n, i, j)
    if i == j:
        return 0, i
    best = None
    split = None
    for k in range(i, j):
        here = (naive_max_cost(dims, i, k) + naive_max_cost(dims, k + 1, j)
                + _mul(dims, i, k + 1, j + 1))
        if best is None or here > best:
            best = here
            split = k
    left = naive_max_optimal(dims, i, split)[1]
    right = naive_max_optimal(dims, split + 1, j)[1]
    return best, (left, right)


def naive_count(dims, i, j):
    """朴素求第 i 到第 j 个矩阵最少次数的加括号方案个数。

    枚举每个断开位置，若左右之和加本次代价等于区间最优值，就把两边的方案数
    相乘后累加；并列最优的多个断开位置都会被算进去。只有一个矩阵时为一。
    """
    n = check_dims(dims)
    _check_pair(n, i, j)
    if i == j:
        return 1
    best = naive_cost(dims, i, j)
    total = 0
    for k in range(i, j):
        here = (naive_cost(dims, i, k) + naive_cost(dims, k + 1, j)
                + _mul(dims, i, k + 1, j + 1))
        if here == best:
            total += naive_count(dims, i, k) * naive_count(dims, k + 1, j)
    return total


def naive_triangle(cost):
    """朴素求多边形三角剖分的最低代价。

    cost 是一串顶点代价。顶点数为 cost 的长度，剖分一个至少三条边的多边形时，
    固定一条边并在其余顶点里挑一个当顶点，代价是三处顶点代价相乘，再加左右两
    块子多边形的代价，取最小者。并列时取顶点位置最小的那个。边数不足三时为
    零。本函数与矩阵链同构，可用来相互印证。
    """
    cost = list(cost)
    for i, d in enumerate(cost):
        if not isinstance(d, int) or isinstance(d, bool):
            raise ChainError("顶点代价必须是整数", position=i, data=str(d))
    return _tri(cost)


def _tri(cost):
    """朴素剖分：固定首尾边，枚举中间顶点，左右各自递归重算。"""
    m = len(cost)
    if m < 3:
        return 0
    best = None
    for r in range(1, m - 1):
        here = (cost[0] * cost[r] * cost[m - 1]
                + _tri(cost[0:r + 1]) + _tri(cost[r:m]))
        if best is None or here < best:
            best = here
    return best


def whole_cost(dims):
    """整条链的最少乘法次数。"""
    n = check_dims(dims)
    return naive_cost(dims, 0, n - 1)


def whole_optimal(dims):
    """整条链的最少乘法次数与一个最优方案。"""
    n = check_dims(dims)
    return naive_optimal(dims, 0, n - 1)


def whole_max_cost(dims):
    """整条链的最大乘法次数。"""
    n = check_dims(dims)
    return naive_max_cost(dims, 0, n - 1)


def whole_max_optimal(dims):
    """整条链的最大乘法次数与一个对应方案。"""
    n = check_dims(dims)
    return naive_max_optimal(dims, 0, n - 1)


def whole_count(dims):
    """整条链最少次数的加括号方案个数。"""
    n = check_dims(dims)
    return naive_count(dims, 0, n - 1)


def plan_to_string(dims, plan):
    """把一个方案还原成括号字符串。

    叶子直接写矩阵下标；每个内部节点都写出一对括号把左右包住。矩阵个数为一
    时结果是那个下标。
    """
    n = check_dims(dims)
    if n < 2:
        return "" if plan is None else str(plan)
    return _plan_text(plan)


def _plan_text(plan):
    """递归把一个嵌套方案记成带括号的字符串。"""
    if isinstance(plan, int):
        return str(plan)
    return "(" + _plan_text(plan[0]) + _plan_text(plan[1]) + ")"


def parse_plan(dims, text):
    """朴素解析括号串，返回嵌套方案；非法串抛 ChainError。

    叶子写单个矩阵下标，内部节点写成一左括号后跟左右两个子表达式再跟一个
    右括号，空白忽略。串里出现非法字符、括号不配对、下标越界或有剩余内容都
    抛 ChainError。
    """
    n = check_dims(dims)
    if n < 2:
        raise ChainError("矩阵个数不足两个，没有可解析的括号结构", position=0,
                         data=str(text))
    clean = "".join(text.split())
    plan, pos = _parse(clean, 0, n)
    if pos != len(clean):
        raise ChainError("括号串有剩余内容", position=pos, data=str(text))
    return plan


def _parse(text, pos, n):
    """自 pos 起解析一个子表达式，返回方案与新位置。"""
    if pos >= len(text):
        raise ChainError("括号串提前结束", position=pos, data=text)
    ch = text[pos]
    if ch.isdigit():
        d = int(ch)
        if d >= n:
            raise ChainError("矩阵下标越界", position=pos, data=text)
        return d, pos + 1
    if ch != "(":
        raise ChainError("括号串含非法字符", position=pos, data=text)
    left, pos = _parse(text, pos + 1, n)
    right, pos = _parse(text, pos, n)
    if pos >= len(text) or text[pos] != ")":
        raise ChainError("括号不配对", position=pos, data=text)
    return (left, right), pos + 1


def _leaves(plan):
    """按从左到右的顺序产出方案里的矩阵下标。"""
    if isinstance(plan, int):
        yield plan
    else:
        for x in _leaves(plan[0]):
            yield x
        for x in _leaves(plan[1]):
            yield x


def _walk_cost(dims, plan):
    """递归求给定方案的乘法次数，每层重扫左右两块的叶子端点。"""
    if isinstance(plan, int):
        return 0
    a = next(iter(_leaves(plan[0])))
    right = list(_leaves(plan[1]))
    b = right[0]
    c = right[-1]
    return (_walk_cost(dims, plan[0]) + _walk_cost(dims, plan[1])
            + _mul(dims, a, b, c + 1))


def naive_plan_cost(dims, plan_text):
    """朴素从括号串算乘法次数：先解析出结构，再逐层重扫叶子端点累加代价。

    括号串写作矩阵下标加括号，例如两个矩阵相乘写作 (01)，三个写作 (0(12))。
    每一对括号是一次矩阵乘法，重扫它左右两块得到操作数维度，累加相乘代价。
    串非法或维度对不上时抛 ChainError。
    """
    check_dims(dims)
    plan = parse_plan(dims, plan_text)
    return _walk_cost(dims, plan)
