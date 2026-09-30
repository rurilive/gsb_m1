"""卡特兰数与合法括号序列的朴素实现。

当前每条能力都走同一条笨路：求第 n 个卡特兰数时用求和形式的递推式，对每个
下标 i 再把两侧的卡特兰数各自递归展开；枚举长度为 2n 的合法括号序列时，先把
全部长度为 2n 的括号串逐条枚举出来，再对每一条单独判合法性；判断一个括号串是否
合法靠一个栈逐字符模拟；求一个合法序列的合法前缀计数，则对每一个前缀单独重判
一遍。这些路径结果都对、口径固定，但规模一上去就按指数或二的次方量级膨胀。全部
实现只用标准库，且不依赖任何模块级可变状态。
"""


class CatalanxError(Exception):
    """本模块所有错误的基类，上层只认这一个根。"""


class TypeMismatchError(CatalanxError):
    """入口收到的参数类型不对时抛出。"""


class InvalidBracketError(CatalanxError):
    """括号串只允许圆括号，出现别的字符时抛出。"""


class OutOfRangeError(CatalanxError):
    """序号越界，或字典序名次越界时抛出。"""


def _check_n(n):
    """求卡特兰数前校验 n 是非负整数且不是布尔值。"""
    if isinstance(n, bool) or not isinstance(n, int):
        raise TypeMismatchError("n 必须是整数")
    if n < 0:
        raise OutOfRangeError("n 不能为负")


def _check_string(s):
    """校验括号串是字符串且只含左右圆括号。"""
    if not isinstance(s, str):
        raise TypeMismatchError("括号序列必须是字符串")
    for ch in s:
        if ch != "(" and ch != ")":
            raise InvalidBracketError("括号序列只允许圆括号")


def _check_index(k):
    """取第 k 个序列前校验 k 是普通整数。"""
    if isinstance(k, bool) or not isinstance(k, int):
        raise TypeMismatchError("序号必须是整数")


class Catalanx:
    """卡特兰数与合法括号序列的朴素求解器。

    每个方法都是只读的，不在实例或模块上缓存任何中间结果，同一个实例重复调用
    给出完全一致的答案；计数属性在每次入口调用开始时归零后重新累加。
    """

    def __init__(self):
        self.recursion_steps = 0
        self.recurrence_visits = 0
        self.full_enumeration_count = 0

    def _reset_counters(self):
        self.recursion_steps = 0
        self.recurrence_visits = 0
        self.full_enumeration_count = 0

    def catalan_recursive(self, n):
        """用求和形式的递推式求第 n 个卡特兰数，对每个位置再递归展开。

        第 n 个数按前 n 项两两相乘求和得到，每一项都重新递归展开，重复子问题被
        反复计算，规模稍大就退化成指数级。入口先校验 n，再把计数归零重算。
        """
        _check_n(n)
        self._reset_counters()
        return self._catalan_recursive_core(n)

    def _catalan_recursive_core(self, n):
        """求和递推式的递归展开体，递归访问次数记在 recurrence_visits 上。"""
        self.recurrence_visits += 1
        if n < 2:
            return 1
        total = 0
        for i in range(n):
            self.recursion_steps += 1
            left = self._catalan_recursive_core(i)
            right = self._catalan_recursive_core(n - 1 - i)
            total += left * right
        return total

    def is_valid(self, s):
        """用栈逐字符模拟判断一个括号串是否合法。"""
        _check_string(s)
        depth = 0
        for ch in s:
            if ch == "(":
                depth += 1
            else:
                depth -= 1
            if depth < 0:
                return False
        return depth == 0

    def valid_prefix_count(self, s):
        """统计一个合法括号串的合法前缀计数，对每个前缀单独重判。"""
        _check_string(s)
        count = 0
        for i in range(1, len(s) + 1):
            if self.is_valid(s[:i]):
                count += 1
        return count

    def enumerate_all(self, n):
        """枚举长度为 2n 的全部括号串，再逐个判合法性，返回合法序列列表。

        先把二的 2n 次方条候选串全部生成出来，再对每一条调用栈模拟判定，规模一大
        就在候选枚举上卡死；全枚举条数记在 full_enumeration_count 上。
        """
        _check_n(n)
        self.full_enumeration_count = 0
        length = 2 * n
        result = []
        for mask in range(1 << length):
            candidate = []
            for pos in range(length):
                bit = (mask >> pos) & 1
                candidate.append("(" if bit == 0 else ")")
            text = "".join(candidate)
            self.full_enumeration_count += 1
            if self.is_valid(text):
                result.append(text)
        return result

    def count_sequences(self, n):
        """长度为 2n 的合法括号序列条数，先把全部候选枚举出来再计数。"""
        _check_n(n)
        return len(self.enumerate_all(n))

    def count_monotone_paths(self, n):
        """网格上每步向右或向上、且始终不越过对角线时的全部路径条数。

        同样先枚举全部长度为 2n 的向右或向上序列，再靠一个平衡变量判定是否始终
        不越界，最后计数。
        """
        _check_n(n)
        length = 2 * n
        total = 0
        for mask in range(1 << length):
            balance = 0
            ok = True
            for pos in range(length):
                bit = (mask >> pos) & 1
                balance += 1 if bit == 0 else -1
                if balance < 0:
                    ok = False
                    break
            if ok and balance == 0:
                total += 1
        return total

    def list_sequence(self, n, k):
        """返回全部合法序列里按字典序排第 k 个，序号从零起算。

        先把序列全部枚举出来后再升序排序，再按下标取值。
        """
        _check_index(k)
        seqs = self.enumerate_all(n)
        seqs.sort()
        if k < 0 or k >= len(seqs):
            raise OutOfRangeError("序号越界")
        return seqs[k]

    def rank_sequence(self, s):
        """求一个合法括号序列在全部合法序列里的字典序名次，从零起算。

        先把同长度的全部合法序列枚举排序再数它的位置。
        """
        _check_string(s)
        if not self.is_valid(s):
            raise InvalidBracketError("待排名次的序列不合法")
        n = len(s) // 2
        seqs = self.enumerate_all(n)
        seqs.sort()
        return seqs.index(s)
