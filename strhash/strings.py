"""字符串子串判定的朴素实现。

当前所有判定都走同一条笨路：要比较两个子串，就把两段切片逐字符比一遍；
要求两个后缀的最长公共前缀，就从头逐字符往下扫；要查一个模式有没有作为
子串出现，就把每个起始位置的等长切片拿出来与模式整体比较。判定一多就是
平方量级，文本稍长就慢得明显，但每个结果都是对的，且不依赖任何全局状态。
"""


class HashError(Exception):
    """本模块所有错误的基类，上层只认这一个根。"""


class HashIndexError(HashError):
    """下标越界或下标类型非法。"""


class NaiveStr:
    """在一段不可变文本上做朴素子串判定。

    文本一经构造即不可变，所有判定方法都是只读的，也不在实例上缓存任何
    中间结果，同一个实例重复调用给出完全一致的答案。
    """

    def __init__(self, text):
        if not isinstance(text, str):
            raise TypeError("文本必须是字符串")
        self._text = text

    def __repr__(self):
        return f"<NaiveStr {len(self._text)} chars>"

    def __len__(self):
        """文本长度。"""
        return len(self._text)

    @property
    def text(self):
        """构造时传入的原始文本。"""
        return self._text

    def _check_index(self, i, what="下标"):
        """校验单个下标：必须是整数且在合法范围内。"""
        if not isinstance(i, int) or isinstance(i, bool):
            raise HashIndexError(f"{what}必须是整数")
        if i < 0 or i >= len(self._text):
            raise HashIndexError(f"{what}越界: {i}")

    def _check_range(self, start, end):
        """校验半开区间，允许 start 等于 end（空串），空串只允许出现在末尾。"""
        if not isinstance(start, int) or isinstance(start, bool):
            raise HashIndexError("区间起点必须是整数")
        if not isinstance(end, int) or isinstance(end, bool):
            raise HashIndexError("区间终点必须是整数")
        n = len(self._text)
        if start < 0 or start > n:
            raise HashIndexError(f"区间起点越界: {start}")
        if end < start or end > n:
            raise HashIndexError(f"区间终点越界: {end}")

    def substr(self, start, end):
        """取半开区间内的子串切片，原样返回。"""
        self._check_range(start, end)
        return self._text[start:end]

    def is_equal(self, a_start, a_end, b_start, b_end):
        """判定两段子串是否相等，逐字符比较整段切片。"""
        self._check_range(a_start, a_end)
        self._check_range(b_start, b_end)
        return self._text[a_start:a_end] == self._text[b_start:b_end]

    def lcp(self, i, j):
        """两个后缀的最长公共前缀长度，从首字符逐个往下比。"""
        self._check_index(i, "左下标")
        self._check_index(j, "右下标")
        n = len(self._text)
        k = 0
        while i + k < n and j + k < n and self._text[i + k] == self._text[j + k]:
            k += 1
        return k

    def contains(self, pattern):
        """模式是否作为子串出现，逐个起始位置切出等长切片比较。"""
        if not isinstance(pattern, str):
            raise TypeError("模式必须是字符串")
        n = len(self._text)
        m = len(pattern)
        if m == 0:
            return True
        if m > n:
            return False
        for i in range(n - m + 1):
            if self._text[i:i + m] == pattern:
                return True
        return False

    def count_pattern(self, pattern):
        """模式在文本中出现的次数，含自重叠，逐位置比较整段切片。"""
        if not isinstance(pattern, str):
            raise TypeError("模式必须是字符串")
        n = len(self._text)
        m = len(pattern)
        if m == 0:
            return n + 1
        if m > n:
            return 0
        count = 0
        for i in range(n - m + 1):
            if self._text[i:i + m] == pattern:
                count += 1
        return count

    def count_distinct_substrings(self):
        """把全部子串切片塞进集合去重后计数。"""
        seen = set()
        n = len(self._text)
        for i in range(n):
            for j in range(i + 1, n + 1):
                seen.add(self._text[i:j])
        return len(seen)

    def is_rotation(self, other):
        """判定另一串是否为本串的循环同构，逐位置切出等长块比较。

        朴素做法：把本串与自身拼接，再检查另一串是否作为子串出现在其中，
        复用的是逐位置整段比较那条路。空串与空串互为循环同构。
        """
        if not isinstance(other, str):
            raise TypeError("待判定串必须是字符串")
        if len(other) != len(self._text):
            return False
        if len(self._text) == 0:
            return True
        doubled = self._text + self._text
        m = len(other)
        for i in range(len(doubled) - m + 1):
            if doubled[i:i + m] == other:
                return True
        return False

    def compare_count(self, a_start, a_end, b_start, b_end):
        """把这两段子串逐字符比较实际走到的字符比对次数如实报出来。

        朴素做法：从两段切片的首字符并排比下去，相等到某一段耗尽或首次
        不同为止，把走过的比较步数原样返回。这段计数是后续与常数级哈希
        取值对照的代价量。
        """
        self._check_range(a_start, a_end)
        self._check_range(b_start, b_end)
        left = self._text[a_start:a_end]
        right = self._text[b_start:b_end]
        steps = 0
        limit = min(len(left), len(right))
        while steps < limit:
            steps += 1
            if left[steps - 1] != right[steps - 1]:
                break
        return steps
