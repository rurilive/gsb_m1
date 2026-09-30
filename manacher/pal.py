"""pal: 改造前的朴素回文统计工具。

这里只有最直接的做法：判断一段是不是回文就逐字符从两端往中间比；求最长
回文就枚举每一个子串逐个判断再取最长；数回文子串总数、数本质不同的回文
种类、求某个回文出现了多少次，都先把每一个子串列出来再逐个判断；对某个
中心求最长回文半径，也朝两边一格一格地暴力扩展。整体是平方级的，文本一
长就撑不住。本文件是改造前的基线，不包含任何线性回文结构。
"""

__all__ = ["Erro", "BruteStats"]


class Erro(Exception):
    """本模块所有自定义错误的基类。"""


class BruteStats:
    """朴素的回文统计工具，内部持有一份不可变的字符串。

    构造时把文本存下来，之后所有方法都在它上面工作，不再改动这份文本。
    非法参数一律当场抛出 Erro，不做悄悄修正。
    """

    def __init__(self, text):
        if not isinstance(text, str):
            raise Erro("text 必须是字符串")
        self._text = text

    @property
    def text(self):
        return self._text

    def __len__(self):
        return len(self._text)

    @staticmethod
    def _check_lo_hi(lo, hi, n):
        if not isinstance(lo, int) or not isinstance(hi, int):
            raise Erro("下标必须是整数")
        if lo < 0 or hi > n or lo > hi:
            raise Erro("下标越界或区间非法")

    def is_palindrome(self, lo, hi):
        """判断半开区间 [lo, hi) 上的子串是不是回文，逐字符从两端比对。"""
        n = len(self._text)
        self._check_lo_hi(lo, hi, n)
        i, j = lo, hi - 1
        while i < j:
            if self._text[i] != self._text[j]:
                return False
            i += 1
            j -= 1
        return True

    def longest_palindrome(self):
        """枚举全部子串逐个判断回文，返回最长的那个子串内容。

        空串返回空串。长度相同时取起始下标较小的那一个。
        """
        n = len(self._text)
        best = ""
        for lo in range(n):
            for hi in range(lo + 1, n + 1):
                if hi - lo <= len(best):
                    continue
                if self.is_palindrome(lo, hi):
                    best = self._text[lo:hi]
        return best

    def longest_palindrome_len(self):
        """返回最长回文子串的长度，空串为长度零。"""
        return len(self.longest_palindrome())

    def count_palindromes(self):
        """枚举全部子串逐个判断回文并计数，返回回文子串的总数。

        含重复位置在内全部计入，同一个回文在不同位置出现分别计数，重叠也算。
        """
        n = len(self._text)
        total = 0
        for lo in range(n):
            for hi in range(lo + 1, n + 1):
                if self.is_palindrome(lo, hi):
                    total += 1
        return total

    def distinct_palindromes(self):
        """枚举全部子串，收集互不相同的回文子串内容。

        返回一个集合，重复出现的同一种回文只算一次，空串不计入。
        """
        n = len(self._text)
        seen = set()
        for lo in range(n):
            for hi in range(lo + 1, n + 1):
                if self.is_palindrome(lo, hi):
                    seen.add(self._text[lo:hi])
        return seen

    def count_distinct_palindromes(self):
        """返回本质不同回文子串的种数。"""
        return len(self.distinct_palindromes())

    def occurrence_count(self, pattern):
        """子串 pattern 在文本中作为回文出现的次数。

        pattern 必须是回文，否则抛 Erro。逐一枚举长度等于它的区间，判断是不是
        回文且内容相等，重叠出现也分别计数。
        """
        if not isinstance(pattern, str):
            raise Erro("pattern 必须是字符串")
        if len(pattern) == 0:
            raise Erro("pattern 不能是空串")
        if pattern != pattern[::-1]:
            raise Erro("pattern 必须是回文")
        n = len(self._text)
        m = len(pattern)
        total = 0
        for lo in range(0, n - m + 1):
            hi = lo + m
            if self._text[lo:hi] == pattern and self.is_palindrome(lo, hi):
                total += 1
        return total

    def each_center_max(self, k):
        """对给定中心向两边暴力扩展，求最长回文半径。

        中心口径：下标从零开始，共二乘以长度再加一这么多个中心，编号 k 在
        零到二乘以长度之间。k 为偶数时是下标 k 除以二的字符中心，k 为奇数
        时是它左边那个字符与右边那个字符之间的间隙中心。返回半径，字符中心
        的半径是它向两边对称展开能覆盖的字符个数，最小为一，单字符本身也算
        一个；间隙中心的半径是它向两边对称展开能配上的对数，零表示两侧第一
        对字符就不相等。
        """
        n = len(self._text)
        if not isinstance(k, int):
            raise Erro("中心必须是整数")
        if k < 0 or k > 2 * n:
            raise Erro("中心越界")
        if k % 2 == 0:
            i = k // 2 - 1
            j = k // 2 + 1
            radius = 1
        else:
            i = k // 2
            j = k // 2 + 1
            radius = 0
        while i >= 0 and j < n and self._text[i] == self._text[j]:
            radius += 1
            i -= 1
            j += 1
        return radius
