"""朴素子串统计：枚举全部起点与全部子串。

改造前的基线实现。功能正确，但每个能力的代价都随串长的平方量级上涨：

- 求本质不同子串个数：枚举全部起点的全部子串塞进集合，子串个数是平方量级，
  每个子串还要切片与哈希，整体立方量级；
- 求某子串出现次数：枚举全部起点逐个比对；
- 求最长重复子串：枚举全部子串，统计每个子串出现次数再取最长；
- 判断子串是否存在：同样靠枚举。

模块不含后缀自动机，也没有任何线性做法——那是本次改造要补的目标。
"""


class SubstringStats:
    """朴素子串统计器。

    构造时接收一个待统计的字符串，之后各方法各自枚举全部起点与全部子串完成计算。
    """

    def __init__(self, text):
        if not isinstance(text, str):
            raise TypeError("text 必须是字符串")
        self._text = text

    @property
    def text(self):
        return self._text

    def _all_substrings(self):
        """枚举全部起点、全部长度的子串，不去重。"""
        n = len(self._text)
        for i in range(n):
            for j in range(i + 1, n + 1):
                yield self._text[i:j]

    def distinct_substring_count(self):
        """本质不同子串个数：全部子串去重后的大小。

        朴素做法压根不区分重复，先枚举出一切子串（平方量级），
        再靠集合去重，比较与切片都要付出代价。
        """
        seen = set()
        for sub in self._all_substrings():
            seen.add(sub)
        return len(seen)

    def count_occurrences(self, pattern):
        """某子串在原串里的出现次数（含全部重叠出现）。

        枚举全部起点，逐个切出与 pattern 等长的片段做相等判断。
        """
        if not isinstance(pattern, str):
            raise TypeError("pattern 必须是字符串")
        if pattern == "":
            return len(self._text) + 1
        n = len(self._text)
        m = len(pattern)
        total = 0
        for i in range(n - m + 1):
            if self._text[i:i + m] == pattern:
                total += 1
        return total

    def contains(self, pattern):
        """判断某子串是否存在：出现次数大于零即为真。"""
        return self.count_occurrences(pattern) > 0

    def longest_repeated_substring(self):
        """最长重复子串：在所有出现次数不少于二的子串里取最长的一个。

        朴素做法枚举全部子串，逐个子串再数一遍出现次数，取最长。
        没有重复子串时返回空串。
        """
        best = ""
        for sub in self._all_substrings():
            if len(sub) <= len(best):
                continue
            if self.count_occurrences(sub) >= 2:
                best = sub
        return best

    def distinct_substrings(self):
        """本质不同子串的集合，按首次出现的顺序无法保证，这里返回升序列表。"""
        seen = set()
        for sub in self._all_substrings():
            seen.add(sub)
        return sorted(seen)
