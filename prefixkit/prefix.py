"""prefixkit 的朴素实现（改造前基线）。

对字符串只做最直白的处理：求每个前缀的前缀函数值，就把该前缀的每一个真前缀都
枚举出来、逐字符比对，看它是不是同时也是后缀，取最长者；在文本里找一个模式的
全部出现位置，就对每一个对齐位置从前往后逐字符暴力比对；统计每个前缀在原串里
的出现次数、判断最短循环节与周期、统计各前缀出现次数，也都是先把候选人枚举
出来再逐个验证。功能正确，规模一大就是平方甚至立方级，也没有任何一次线性扫描
复用已完成前缀函数的机制可用。
"""


class PrefixError(Exception):
    """本库所有异常的基类。"""


class InvalidInputError(PrefixError, ValueError):
    """违反输入口径时抛出（非字符串、下标越界、空模式、下标非整数等）。"""


def _check_text(value, name="字符串"):
    """文本校验：必须是字符串。"""
    if not isinstance(value, str):
        raise InvalidInputError(f"{name}必须是字符串")
    return value


def _check_index(k, length):
    """下标校验：整数，且 0 <= k <= length。"""
    if isinstance(k, bool) or not isinstance(k, int):
        raise InvalidInputError("下标必须是整数")
    if k < 0 or k > length:
        raise InvalidInputError("下标越界")
    return k


def _naive_longest_border(s, k):
    """求 s 前 k 个字符的最长真前后缀长度，逐字符比对，返回 (长度, 比较次数)。

    直接枚举所有候选长度，从长到短，对每个候选逐字符比对。
    """
    steps = 0
    for length in range(k - 1, 0, -1):
        matched = True
        for j in range(length):
            steps += 1
            if s[j] != s[k - length + j]:
                matched = False
                break
        if matched:
            return length, steps
    return 0, steps


def _naive_prefix_function(s):
    """朴素前缀函数：每个前缀各自枚举真前缀，返回 (值列表, 比较次数)。

    值列表长度为 len(s) + 1，第 0 位固定为 0。
    """
    n = len(s)
    values = [0]
    steps = 0
    for k in range(1, n + 1):
        length, cost = _naive_longest_border(s, k)
        values.append(length)
        steps += cost
    return values, steps


def _naive_occurrences(pattern, text):
    """朴素单模式查找：对每个对齐位置逐字符暴力比对，返回 (位置列表, 比较次数)。"""
    steps = 0
    hits = []
    lp = len(pattern)
    lt = len(text)
    for start in range(0, lt - lp + 1):
        matched = True
        for j in range(lp):
            steps += 1
            if text[start + j] != pattern[j]:
                matched = False
                break
        if matched:
            hits.append(start)
    return hits, steps


class PrefixKit:
    """字符串前缀函数与周期的朴素实现。

    prefix_function()：朴素前缀函数，返回长度 n+1 的列表。
    prefix_value(k)：第 k 个前缀（长度为 k）的前缀函数值。
    find_occurrences(text)：模式在文本中全部出现位置的起始下标，升序。
    count_occurrences(text)：出现位置个数。
    count_prefix_occurrences()：每个前缀在原串中的出现次数（含互相重叠）。
    period_info()：最短循环节与周期判定信息。
    min_period()：最短循环节长度，无真周期时即整串长度。
    prefix_steps()：最近一次求前缀函数的比较次数。
    search_steps()：最近一次查找的比较次数。
    """

    def __init__(self, pattern=""):
        self._pattern = _check_text(pattern, "模式")
        self._prefix_steps = 0
        self._search_steps = 0

    def pattern(self):
        return self._pattern

    def prefix_function(self):
        values, steps = _naive_prefix_function(self._pattern)
        self._prefix_steps = steps
        return values

    def prefix_value(self, k):
        _check_index(k, len(self._pattern))
        values, steps = _naive_prefix_function(self._pattern[:k])
        self._prefix_steps = steps
        return values[k]

    def find_occurrences(self, text):
        _check_text(text, "文本")
        if not self._pattern:
            raise InvalidInputError("空模式不允许查找")
        hits, steps = _naive_occurrences(self._pattern, text)
        self._search_steps = steps
        return hits

    def count_occurrences(self, text):
        return len(self.find_occurrences(text))

    def count_prefix_occurrences(self):
        s = self._pattern
        n = len(s)
        counts = {}
        for length in range(1, n + 1):
            block = s[:length]
            total = 0
            for start in range(0, len(s) - length + 1):
                if s[start:start + length] == block:
                    total += 1
            counts[length] = total
        return counts

    def period_info(self):
        """判断整串是否为一个更短块的整数次重复。

        枚举所有能整除长度的块长，从短到长，验证是否由该块整段重复拼成。
        找到最短的即为循环节；找不到真周期时不算周期串。
        """
        s = self._pattern
        n = len(s)
        if n == 0:
            return {"is_periodic": False, "period": None, "exponent": 0}
        for length in range(1, n):
            if n % length == 0 and s[:length] * (n // length) == s:
                return {"is_periodic": True, "period": length, "exponent": n // length}
        return {"is_periodic": False, "period": None, "exponent": 1}

    def min_period(self):
        info = self.period_info()
        if info["is_periodic"]:
            return info["period"]
        return len(self._pattern)

    def prefix_steps(self):
        return self._prefix_steps

    def search_steps(self):
        return self._search_steps
