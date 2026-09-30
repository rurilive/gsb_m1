"""mpmatch 的朴素多模式查找实现（改造前的现状）。

现在只有一条路径：对每一个模式，从文本的每个起点起逐字符和该模式
比对，能对上就记下这个起点。没有字典树，没有失败指针，一次查找要
按模式个数与文本长度成倍地重复比对。逐位置结尾命中集合、命中汇总
与字典树搭配失败指针的自动机见任务描述。
"""


class Erro(Exception):
    """本模块所有对外异常的公共基类。"""


class PatternError(Erro):
    """模式集合或模式本身的非法输入。"""


def _check_patterns(patterns):
    """模式集合必须是字符串序列，成员须是字符串，返回去重后的元组。"""
    if isinstance(patterns, (str, bytes)) or not hasattr(patterns, "__iter__"):
        raise PatternError("patterns must be a sequence of str")
    seen = []
    mark = set()
    for item in patterns:
        if not isinstance(item, str):
            raise PatternError("each pattern must be a str")
        if item == "":
            raise PatternError("pattern must not be empty")
        if item not in mark:
            mark.add(item)
            seen.append(item)
    return tuple(seen)


def _check_text(text):
    """文本必须是字符串，允许为空串。"""
    if not isinstance(text, str):
        raise PatternError("text must be a str")
    return text


class Matcher:
    """一批模式串，查找只有逐模式、逐位置直接比对这一种。"""

    def __init__(self, patterns):
        self._patterns = _check_patterns(patterns)
        self._compare_count = 0

    def patterns(self):
        """按加入顺序返回去重后的模式元组。"""
        return self._patterns

    def __len__(self):
        return len(self._patterns)

    def __contains__(self, pattern):
        return pattern in self._patterns

    def _find_naive(self, pattern, text):
        """朴素查找：每个起点逐字符比对，返回升序起点列表并累计比对次数。"""
        positions = []
        n = len(text)
        m = len(pattern)
        if m == 0 or m > n:
            return positions
        for start in range(n - m + 1):
            ok = True
            for k in range(m):
                self._compare_count += 1
                if text[start + k] != pattern[k]:
                    ok = False
                    break
            if ok:
                positions.append(start)
        return positions

    def reset_compare_count(self):
        """把逐字符比对计数清零。"""
        self._compare_count = 0

    def compare_count(self):
        """自上次清零以来累计比对了多少个字符位置。"""
        return self._compare_count

    def positions(self, pattern, text):
        """返回模式在文本里出现的全部起点，升序，允许重叠。"""
        if not isinstance(pattern, str):
            raise PatternError("pattern must be a str")
        if pattern == "":
            raise PatternError("pattern must not be empty")
        _check_text(text)
        return self._find_naive(pattern, text)

    def count(self, pattern, text):
        """返回模式在文本里出现的次数，允许重叠。"""
        return len(self.positions(pattern, text))

    def find_all(self, text):
        """一次性返回每个模式的全部起点，键为模式，值为升序起点列表。"""
        _check_text(text)
        result = {}
        for pattern in self._patterns:
            result[pattern] = self._find_naive(pattern, text)
        return result

    def exists(self, text):
        """文本里是否存在任意一个模式命中。"""
        _check_text(text)
        for pattern in self._patterns:
            if self._find_naive(pattern, text):
                return True
        return False
