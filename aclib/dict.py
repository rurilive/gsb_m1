"""朴素多模式字典:对每个模式各自扫描一遍文本。

这是"改造前"的基线实现。它维护一组模式串,每次匹配都把每个模式
单独拿到文本上用朴素子串查找走一遍。行为简单直观,但模式一多就会
重复劳动,也无法在一次扫描中同时命中所有模式。
"""


class DictError(Exception):
    """本模块所有字典相关错误的基类。"""


class InvalidPatternError(DictError, ValueError):
    """模式串非法(例如为空串)时抛出。"""


class BruteDict:
    """朴素多模式字典。

    内部按加入顺序保存模式串。所有查询接口都对每个模式分别扫描文本。
    出现次数与出现位置均统计互为重叠的匹配。
    """

    def __init__(self):
        # 模式按加入顺序保存;重复加入同一模式会被忽略。
        self._patterns = []

    def add(self, word):
        """加入一个模式。空模式或非字符串立即报错。"""
        if not isinstance(word, str):
            raise InvalidPatternError("pattern must be a string")
        if word == "":
            raise InvalidPatternError("pattern must not be empty")
        if word not in self._patterns:
            self._patterns.append(word)

    def patterns(self):
        """按加入顺序返回当前全部模式。"""
        return list(self._patterns)

    def count_occurrences(self, text):
        """返回每个模式在文本中出现的总次数(含重叠出现)。"""
        result = {}
        for word in self._patterns:
            result[word] = self._count_one(word, text)
        return result

    def first_match(self, text):
        """返回全局最早的一次出现,形如 (位置, 模式);没有则返回 None。

        同一位置若有多个模式命中,按模式加入顺序取最先加入的那个。
        """
        n = len(text)
        for i in range(n):
            for word in self._patterns:
                if text.startswith(word, i):
                    return (i, word)
        return None

    def matches_in(self, text):
        """返回每个模式在文本中出现的全部起始位置(升序,含重叠)。"""
        result = {}
        for word in self._patterns:
            result[word] = self._positions_one(word, text)
        return result

    def _count_one(self, word, text):
        total = 0
        start = 0
        while True:
            pos = text.find(word, start)
            if pos == -1:
                break
            total += 1
            start = pos + 1
        return total

    def _positions_one(self, word, text):
        positions = []
        start = 0
        while True:
            pos = text.find(word, start)
            if pos == -1:
                break
            positions.append(pos)
            start = pos + 1
        return positions
