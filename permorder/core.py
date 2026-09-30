"""排列生成与字典序的朴素实现。

当前每条能力都走同一条笨路：想拿到一个排列的下一个字典序排列，先把该排列所属
多重集合的全部不重复排列递归枚举出来、排序，再取相邻那一条；想知道某个排列排
第几，也是先把全部排列枚举排序后再数位置；想按序号取排列，同样先枚举全部再下
标取值；判断一个序列是不是另一个的排列，则把两边各自排序后逐位比较。这些路径
结果都对，口径也固定，但元素个数一上去，枚举的排列数就按阶乘量级膨胀。全部实现
只用标准库，且不依赖任何模块级可变状态。
"""


class PermOrderError(Exception):
    """本模块所有错误的基类，上层只认这一个根。"""


class TypeMismatchError(PermOrderError):
    """入口收到的参数不是可比较的序列时抛出。"""


class OutOfRangeError(PermOrderError):
    """按序号取排列时序号越界抛出。"""


class UnsortedBasisError(PermOrderError):
    """反查排列时给定的基准多重集合不是升序时抛出。"""


def _is_sequence(value):
    """只认列表与元组这类定长可枚举且可切片的序列。"""
    return isinstance(value, (list, tuple))


def _as_tuple(seq):
    """把输入规整成元组，顺便校验它是不是合法的可比较序列。"""
    if not _is_sequence(seq):
        raise TypeMismatchError("参数必须是列表或元组")
    items = tuple(seq)
    try:
        tuple(sorted(items))
    except TypeError as exc:
        raise TypeMismatchError("元素之间必须可以互相比较") from exc
    return items


def _is_sorted_ascending(items):
    """逐位判断序列是否非降序。"""
    for i in range(1, len(items)):
        if items[i - 1] > items[i]:
            return False
    return True


def _distinct_permutations(seq):
    """递归枚举 seq 的全部不重复排列，排序后返回。

    对每一个候选都用一张已用标记表判断哪个位置的元素还没被取过，取满长度就得到
    一个排列；重复元素会产出同一个元组，用集合去重后再统一升序排序。同一输入每次
    跑出来的顺序完全一致，结果只由输入决定。
    """
    items = list(seq)
    n = len(items)
    used = [False] * n
    current = []
    seen = set()
    collected = []

    def walk():
        if len(current) == n:
            candidate = tuple(current)
            if candidate not in seen:
                seen.add(candidate)
                collected.append(candidate)
            return
        for i in range(n):
            if used[i]:
                continue
            used[i] = True
            current.append(items[i])
            walk()
            current.pop()
            used[i] = False

    walk()
    collected.sort()
    return collected


def _check_index(k):
    """按序号取排列前，校验序号是普通整数而不是布尔值。"""
    if isinstance(k, bool) or not isinstance(k, int):
        raise TypeMismatchError("序号必须是整数")


class PermOrder:
    """排列字典序的朴素求解器，全部能力都靠递归枚举加排序。

    每个方法都是只读的，不在实例或模块上缓存任何中间结果，同一个实例重复调用
    给出完全一致的答案。
    """

    def next_permutation(self, items):
        """求下一个字典序排列，靠枚举全部排列排序后取相邻那条。

        到达最大排列时回绕到最小排列。传入列表时就地改写该列表，同时把结果也
        作为返回值给出。
        """
        seq = _as_tuple(items)
        perms = _distinct_permutations(seq)
        position = perms.index(seq)
        following = perms[(position + 1) % len(perms)]
        if isinstance(items, list):
            items[:] = list(following)
        return list(following)

    def kth_permutation(self, seq, k):
        """求多重集合按字典序排第 k 个的排列，序号从零起算。

        先按当前元素自身把多重集合规整出来，再枚举全部不重复排列排序后按下标取。
        """
        _check_index(k)
        basis = _as_tuple(seq)
        perms = _distinct_permutations(basis)
        if k < 0 or k >= len(perms):
            raise OutOfRangeError("序号越界")
        return list(perms[k])

    def rank(self, perm):
        """求一个排列在它所属多重集合的全部不重复排列里的字典序名次，从零起算。"""
        seq = _as_tuple(perm)
        perms = _distinct_permutations(seq)
        return perms.index(seq)

    def unrank(self, basis, k):
        """按名次反查排列，基准多重集合必须以升序给出。

        与按序号取排列的差别在于，这里的基准是明确交给调用者的既定次序，不是
        从序列自身推出来的多重集合。
        """
        _check_index(k)
        items = _as_tuple(basis)
        if not _is_sorted_ascending(items):
            raise UnsortedBasisError("基准多重集合必须升序给出")
        perms = _distinct_permutations(items)
        if k < 0 or k >= len(perms):
            raise OutOfRangeError("序号越界")
        return list(perms[k])

    def is_permutation(self, a, b):
        """判断一个序列是不是另一个的排列，把两边各自排序后逐位比较。"""
        left = sorted(_as_tuple(a))
        right = sorted(_as_tuple(b))
        if len(left) != len(right):
            return False
        for i in range(len(left)):
            if left[i] != right[i]:
                return False
        return True
