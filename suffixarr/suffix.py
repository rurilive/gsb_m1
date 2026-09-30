"""朴素后缀数组工具。

当前实现全部以最直白的方式完成：把全部后缀切片取出后整体排序得到下标
序列，逐对后缀从头逐字符比较求最长公共前缀，用两层切片把全部子串塞进
集合去重计数，用逐个起始位置的子串比较统计模式出现次数，最长重复子串
则枚举每一对后缀。这些路径规模一大就慢，但结果正确。
"""


class SuffixError(Exception):
    """本模块所有错误的基类，上层只认这一个根。"""


class SuffixIndexError(SuffixError):
    """下标越界或下标类型非法。"""


class NaiveSuffix:
    """在一段不可变文本上做朴素后缀查询。

    文本一经构造即不可变，所有查询方法都是只读的。
    """

    def __init__(self, text):
        if not isinstance(text, str):
            raise TypeError("文本必须是字符串")
        self._text = text

    def __repr__(self):
        return f"<NaiveSuffix {len(self._text)} chars>"

    def __len__(self):
        """文本长度。"""
        return len(self._text)

    @property
    def text(self):
        """构造时传入的原始文本。"""
        return self._text

    def _check_index(self, i, what="下标"):
        if not isinstance(i, int) or isinstance(i, bool):
            raise SuffixIndexError(f"{what}必须是整数")
        if i < 0 or i >= len(self._text):
            raise SuffixIndexError(f"{what}越界: {i}")

    def suffix_array(self):
        """枚举全部后缀并整体排序，返回排序后的起始下标序列。

        朴素做法：对每个下标切片出完整后缀，整体排序。等值后缀之间按
        下标升序定序，保证结果唯一确定。
        """
        n = len(self._text)
        return sorted(range(n), key=lambda i: self._text[i:])

    def lcp_of(self, i, j):
        """逐字符比较两个后缀，返回最长公共前缀长度。"""
        self._check_index(i, "左下标")
        self._check_index(j, "右下标")
        n = len(self._text)
        k = 0
        while i + k < n and j + k < n and self._text[i + k] == self._text[j + k]:
            k += 1
        return k

    def count_pattern(self, pattern):
        """统计模式 pattern 在文本中出现的次数（含自重叠）。

        朴素做法：挨个起始位置切出等长子串与模式比较。模式为空串时按
        约定返回文本长度加一，也就是每一个合法插入位置各算一次。
        """
        if not isinstance(pattern, str):
            raise TypeError("模式必须是字符串")
        n = len(self._text)
        m = len(pattern)
        if m == 0:
            return n + 1
        count = 0
        for i in range(n - m + 1):
            if self._text[i:i + m] == pattern:
                count += 1
        return count

    def count_distinct_substrings(self):
        """用集合枚举全部子串去重后计数。"""
        seen = set()
        n = len(self._text)
        for i in range(n):
            for j in range(i + 1, n + 1):
                seen.add(self._text[i:j])
        return len(seen)

    def longest_repeated_substring(self):
        """枚举后缀两两之间的最长公共前缀，返回其中最长的那个子串。

        没有任何重复子串时返回空串。有多个同样长的答案时，返回后缀数组
        次序下最先被比较到的那一个，保证结果确定。
        """
        n = len(self._text)
        order = self.suffix_array()
        best = ""
        for a in range(len(order)):
            for b in range(a + 1, len(order)):
                k = self.lcp_of(order[a], order[b])
                if k > len(best):
                    best = self._text[order[a]:order[a] + k]
        return best

    def compare_count(self):
        """把全部后缀整体排序口径下的字符比较次数（可读代价计数）。

        朴素做法：对排序过程中被调用到的每一对后缀，逐字符数到不相等为
        止，累加起来作为可比对的代价量。
        """
        n = len(self._text)
        total = 0
        for i in range(n):
            for j in range(i + 1, n):
                k = self.lcp_of(i, j)
                if i + k < n and j + k < n:
                    k += 1
                total += k
        return total
