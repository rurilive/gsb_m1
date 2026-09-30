"""多模式串匹配：朴素实现（改造前基线）。

每个模式串各自在文本里逐位置滑动比较，命中位置全收集起来。
没有跨模式共享的前缀结构，模式一多就对文本重复扫描。行为是正确的，
作为自动机改造前的基线保留。
"""


class Erro(Exception):
    """本包所有自定义异常的基类。"""


def _naive_find_all(pattern, text):
    """在 text 中逐位置滑动比较 pattern，返回全部命中起始下标（升序）。

    空模式串约定不产生任何命中。文本比模式短时返回空列表。
    """
    hits = []
    n = len(pattern)
    if n == 0:
        return hits
    m = len(text)
    for start in range(m - n + 1):
        if text[start:start + n] == pattern:
            hits.append(start)
    return hits


class Matcher:
    """朴素的多模式匹配器。

    构造时收下一组模式串；查询时对每个模式串分别扫描文本，把命中位置
    全收集起来。命中以 (pattern, start) 表示，start 为命中起始下标。
    """

    def __init__(self, patterns=()):
        self._patterns = list(patterns)

    def patterns(self):
        """返回当前模式串列表（保持构造顺序）。"""
        return list(self._patterns)

    def find_all(self, text):
        """返回字典：模式串 -> 命中起始下标列表（升序）。

        文本比模式长时全量扫描；同一模式串重复出现时，只在字典里留一份键。
        """
        result = {}
        for pattern in self._patterns:
            result[pattern] = _naive_find_all(pattern, text)
        return result

    def find(self, pattern, text):
        """单模式查询：返回 pattern 在 text 中的全部命中起始下标（升序）。"""
        if pattern not in self._patterns:
            raise Erro("模式串不在本次匹配集合内: {!r}".format(pattern))
        return _naive_find_all(pattern, text)

    def count(self, pattern, text):
        """单模式计数：返回 pattern 在 text 中出现的次数。"""
        return len(self.find(pattern, text))

    def search(self, text):
        """对给定文本做一次朴素扫描，返回 (pattern, start) 命中列表。

        结果按模式串在构造列表中的顺序、同模式串内按起始下标升序排列。
        """
        hits = []
        for pattern in self._patterns:
            for start in _naive_find_all(pattern, text):
                hits.append((pattern, start))
        return hits

    def total(self, text):
        """全部模式串在给定文本上的命中总数。"""
        return sum(len(v) for v in self.find_all(text).values())


def build(patterns, text):
    """便捷入口：构造 Matcher 并对 text 扫描一次，返回命中列表。"""
    return Matcher(patterns).search(text)
